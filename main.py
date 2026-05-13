import asyncio
import logging
import uuid
import json
import os
import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from core.config import get_workspace
from core.memory import init_db
from core.orchestrator import process_message
from tool_runtime.loader import load_all_tools, start_watcher, TOOL_REGISTRY

# ── Push Function Registry Handles (Global) ───────────────────────────────────
from tools.daily_briefing import set_push_callback
from core.swarm import set_swarm_push_fn

# Telegram bot stop function — initialized early to avoid UnboundLocalError
_tg_stop = None

active_connections = set()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("aether")

watcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global watcher
    logger.info("Aether is waking up...")
    await init_db()
    load_all_tools()
    watcher = start_watcher()
    logger.info(f"Aether ready. Tools: {list(TOOL_REGISTRY.keys()) or 'none yet'}")

    # ── Register briefing push callback and schedule daily auto-briefing ──
    try:
        from tools.daily_briefing import set_push_callback
        from tools.scheduler import get_scheduler
        from apscheduler.triggers.cron import CronTrigger

        async def _auto_briefing():
            if TOOL_REGISTRY.get("daily_briefing"):
                await TOOL_REGISTRY["daily_briefing"](time_of_day="morning", auto=True)

        scheduler = get_scheduler()
        scheduler.add_job(
            _auto_briefing,
            trigger=CronTrigger(hour=7, minute=0),
            id="auto_morning_briefing",
            replace_existing=True
        )
        logger.info("Daily auto-briefing scheduled at 7:00 AM.")
    except Exception as e:
        logger.warning(f"Auto-briefing schedule failed: {e}")

    # ── Register swarm push (overridden per-session in WS) ─────────
    try:
        from core.swarm import set_swarm_push_fn
        # Default push: just log
        async def _default_push(msg: str, session_id: str = ""):
            logger.info(f"[bg-task] {msg[:100]}")
        set_swarm_push_fn(_default_push)
    except Exception as e:
        logger.warning(f"Push setup failed: {e}")

    # ── Start Telegram Bot ─────────────────────────────────────────────────────────
    global _tg_stop
    try:
        from telegram_bot import start_telegram_bot, stop_telegram_bot
        _tg_stop = stop_telegram_bot
        asyncio.create_task(start_telegram_bot())
    except Exception as e:
        logger.warning(f"Telegram bot init failed: {e}")

    yield
    if watcher:
        watcher.stop()
        watcher.join()
    # Gracefully stop Telegram bot
    try:
        if _tg_stop:
            await _tg_stop()
    except Exception:
        pass
    logger.info("Aether shut down.")

app = FastAPI(title="Aether", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Extreme debug mode: allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "online", 
        "tools": list(TOOL_REGISTRY.keys()),
        "workspace": str(get_workspace())
    }

@app.get("/api/settings")
async def get_settings():
    from core.config import list_settings
    return list_settings()

class SettingsUpdate(BaseModel):
    settings: dict

@app.post("/api/settings")
async def post_settings(update: SettingsUpdate):
    from core.config import save_all_settings
    from telegram_bot import restart_telegram_bot
    try:
        save_all_settings(update.settings)
        # Background task to restart bot so we don't block the UI response
        asyncio.create_task(restart_telegram_bot())
        return {"status": "success", "message": "Settings updated and saved to .env"}
    except Exception as e:
        logger.error(f"Settings save failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.get("/voice/token")
async def get_voice_token():
    try:
        from livekit.api import AccessToken, VideoGrants
        # Use dynamic identity for LiveKit
        uid = os.environ.get("USER_NAME", "User").lower().replace(" ", "_")
        uname = os.environ.get("USER_NAME", "User")
        token = (
            AccessToken(os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
            .with_identity(uid)
            .with_name(uname)
            .with_grants(VideoGrants(room_join=True, room="aether-voice"))
            .to_jwt()
        )
        return {"token": token, "url": os.getenv("LIVEKIT_URL"), "room": "aether-voice"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/tools")
async def list_tools():
    return {"tools": list(TOOL_REGISTRY.keys())}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload file/image — returns base64 for use in chat."""
    try:
        content = await file.read()
        b64 = base64.b64encode(content).decode("utf-8")
        mime = file.content_type or "application/octet-stream"
        file_type = "image" if mime.startswith("image/") else "document"
        return {
            "filename": file.filename,
            "mime_type": mime,
            "type": file_type,
            "base64": b64,
            "size": len(content),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class ExplainRequest(BaseModel):
    text: str

@app.post("/api/quick-explain")
async def quick_explain(req: ExplainRequest):
    text = req.text
    try:
        from core.groq_router import chat
        messages = [
            {"role": "system", "content": "You are Aether. Briefly explain or summarize the user's highlighted text in 2-3 short, clear sentences."},
            {"role": "user", "content": text}
        ]
        response, _, _ = await chat(messages, "general", stream=False)
        return {"explanation": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    session_id = str(uuid.uuid4())
    logger.info(f"New session: {session_id}")

    # 1. Immediate ready signal to bridge the handshake-timeout gap in browsers
    try:
        await websocket.send_text(json.dumps({"type": "ready", "session_id": session_id}))
    except Exception:
        active_connections.remove(websocket)
        return

    # 2. Register push callbacks so background tasks can reach this UI session
    try:
        async def _bg_push(msg: str, sid: str = "", model: str = "assistant", task_msg: str = ""):
            try:
                if task_msg == "start":
                    await websocket.send_text(json.dumps({"type": "start", "session_id": "background"}))
                await websocket.send_text(json.dumps({"type": "chunk", "content": msg}))
                if task_msg == "done":
                    await websocket.send_text(json.dumps({"type": "done", "model": model}))
            except Exception:
                pass

        set_push_callback(_bg_push, session_id)

        # Register this specific session for background swarm updates
        try:
            from core.swarm import set_swarm_push_fn
            
            async def _session_push(msg: str, sid: str = ""):
                if sid == session_id or not sid:
                    await websocket.send_json({"type": "chunk", "content": f"\n\n{msg}"})
            
            set_swarm_push_fn(_session_push, session_id)
        except Exception as e:
            logger.warning(f"Failed to register background callbacks: {e}")
    except Exception as e:
        logger.warning(f"Failed to register background callbacks: {e}")

    try:
        while True:
            try:
                raw = await websocket.receive_text()
                payload = json.loads(raw)
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.warning(f"Malformed WS message: {e}")
                continue

            # 1. Handle technical messages
            msg_type = payload.get("type")
            if msg_type == "ping":
                logger.info(f"Heartbeat [ping] from session {session_id}")
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
                
            if msg_type == "control":
                # Broadcast control message to all other connected clients
                logger.info(f"Control message received: {payload}")
                for conn in list(active_connections):
                    if conn != websocket:
                        try:
                            await conn.send_text(raw)
                        except Exception:
                            pass
                continue
            
            # 2. Extract content
            user_message = payload.get("message", "").strip()
            file_data = payload.get("file_data")  # { type, base64, mime_type, filename }
            auth_reply = payload if msg_type == "auth_reply" else None

            if not user_message and not file_data and not auth_reply:
                continue

            # 3. Process
            async def on_chunk(chunk: str):
                try:
                    await websocket.send_text(json.dumps({"type": "chunk", "content": chunk}))
                except Exception: pass

            await websocket.send_text(json.dumps({"type": "start", "session_id": session_id}))
            
            # Define result ahead of time to avoid NameError
            result = {"model": "unknown", "task_type": "unknown", "response": "Error processing."}

            try:
                result = await process_message(
                    content=user_message if not auth_reply else "",
                    session_id=session_id,
                    on_chunk=on_chunk,
                    file_data=file_data,
                    auth_reply=auth_reply
                )
            except Exception as e:
                logger.error(f"Processing error: {e}")
                await websocket.send_text(json.dumps({"type": "error", "message": f"Processing error: {e}"}))
                continue

            # 4. Finalize
            if result.get("task_type") == "auth_request":
                await websocket.send_text(json.dumps({
                    "type": "auth_request",
                    "message": result.get("response", ""),
                    "auth_id": result.get("auth_id", "")
                }))

            await websocket.send_text(json.dumps({
                "type": "done",
                "model": result.get("model", "unknown"),
                "task_type": result.get("task_type", "unknown"),
            }))

    except WebSocketDisconnect:
        logger.info(f"Session disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Session error: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        # Cleanup callbacks to prevent session memory leaks
        logger.info(f"Cleaning up session: {session_id}")
        try:
            set_push_callback(None, session_id)
            set_swarm_push_fn(None, session_id)
        except Exception as e:
            logger.warning(f"Cleanup error for {session_id}: {e}")

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        print(f"\n[FATAL ERROR] Could not start Aether backend: {e}")
        if "10048" in str(e) or "already in use" in str(e).lower():
            print("\n💡 TIP: Port 8000 is already in use. Close any other Aether windows or run 'stop_ved.bat' first.")
        input("\nPress Enter to exit...")
