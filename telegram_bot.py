"""
Aether Telegram Bot — Full remote control of Aether from your phone.
Runs embedded inside the FastAPI event loop. No separate process needed.
"""

import os
import asyncio
import logging
import base64
import httpx

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("aether.telegram")

_tg_app: Application | None = None
_shared_tg_client = httpx.AsyncClient(timeout=30.0)


def _safe_truncate(text: str, limit: int = 4090) -> str:
    """Truncates text while ensuring Markdown code blocks are closed."""
    if len(text) <= limit:
        return text
    
    truncated = text[:limit]
    # Check if we are inside a code block (odd number of ```)
    if truncated.count("```") % 2 != 0:
        # Close the code block and add ellipsis
        return truncated[:limit-4] + "\n```..."
    return truncated[:limit-3] + "..."


# ── Auth guard ────────────────────────────────────────────────────────────────

def _is_allowed(update: Update) -> bool:
    raw_id = os.getenv("TELEGRAM_ALLOWED_ID", "0")
    allowed_id = int(raw_id) if raw_id.strip().isdigit() else 0
    return update.effective_user and update.effective_user.id == allowed_id


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    ai_name = os.environ.get("AI_NAME", "Aether")
    await update.message.reply_text(
        f"⚡ *{ai_name} is online, Boss.*\n\nAll your tools are ready. "
        "Send any message, use /briefing for your daily brief, or /tools to see what I can do.",
        parse_mode="Markdown"
    )


async def cmd_tools(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    from tool_runtime.loader import TOOL_REGISTRY
    tools_list = "\n".join(f"• `{k}`" for k in sorted(TOOL_REGISTRY.keys()))
    await update.message.reply_text(
        f"🛠 *Loaded Tools ({len(TOOL_REGISTRY)}):*\n{tools_list}",
        parse_mode="Markdown"
    )


async def cmd_briefing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    msg = await update.message.reply_text("⏳ Generating your briefing...")
    from core.orchestrator import process_message
    session_id = f"telegram_{update.effective_chat.id}"
    result = await process_message(content="morning briefing", session_id=session_id)
    resp = result["response"][:4090] or "Briefing unavailable."
    await msg.edit_text(resp)


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text("🗑 Session context cleared. Fresh start, Boss.")


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return

    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    session_id = f"telegram_{chat_id}"

    # Send initial "Thinking..." with retry on timeout
    thinking = None
    for attempt in range(3):
        try:
            thinking = await update.message.reply_text("⏳ Thinking...")
            break
        except Exception as e:
            if attempt == 2:
                logger.warning(f"Could not send thinking message: {e}")
            else:
                await asyncio.sleep(1)

    # Register Telegram-specific swarm push
    try:
        from core.swarm import set_swarm_push_fn
        async def _tg_push(msg: str, sid: str = ""):
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=_safe_truncate(msg))
            except Exception as e:
                logger.warning(f"Telegram background push error: {e}")
        set_swarm_push_fn(_tg_push, session_id)
    except Exception:
        pass

    from core.orchestrator import process_message

    chunks = []
    async def on_chunk(chunk: str):
        chunks.append(chunk)

    result = await process_message(content=text, session_id=session_id, on_chunk=on_chunk)

    # Security Guardrail
    if result.get("task_type") == "auth_request":
        auth_id = result.get("auth_id", "")
        keyboard = [[
            InlineKeyboardButton("✅ Yes, do it",  callback_data=f"auth_yes|{auth_id}|{session_id}"),
            InlineKeyboardButton("❌ No, cancel",  callback_data=f"auth_no|{auth_id}|{session_id}"),
        ]]
        try:
            if thinking:
                await thinking.edit_text(
                    f"⚠️ *Security Guardrail*\n\n{result['response']}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"⚠️ *Security Guardrail*\n\n{result['response']}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.warning(f"Telegram auth send error: {e}")
        return

    response = result.get("response") or "Done, Boss."
    try:
        if thinking:
            await thinking.edit_text(_safe_truncate(response))
        else:
            await update.message.reply_text(_safe_truncate(response))
    except Exception as e:
        logger.warning(f"Telegram reply error: {e}")


# ── Auth button callbacks ─────────────────────────────────────────────────────

async def handle_auth_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    parts = query.data.split("|")
    if len(parts) < 3:
        return

    action, auth_id, session_id = parts[0], parts[1], parts[2]
    confirm = action == "auth_yes"

    from core.orchestrator import process_message
    result = await process_message(
        content="",
        session_id=session_id,
        auth_reply={"auth_id": auth_id, "confirm": confirm}
    )

    status = "✅ *Action executed.*" if confirm else "❌ *Action cancelled.*"
    await query.edit_message_text(
        _safe_truncate(f"{status}\n\n{result.get('response', '')}"),
        parse_mode="Markdown"
    )


# ── Photo handler ─────────────────────────────────────────────────────────────

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return

    msg = await update.message.reply_text("⏳ Analyzing image...")
    photo = update.message.photo[-1]  # highest res
    tg_file = await ctx.bot.get_file(photo.file_id)

    resp = await _shared_tg_client.get(tg_file.file_path)
    b64 = base64.b64encode(resp.content).decode("utf-8")

    caption = update.message.caption or "Describe this image."
    session_id = f"telegram_{update.effective_chat.id}"

    from core.orchestrator import process_message
    result = await process_message(
        content=caption,
        session_id=session_id,
        file_data={"type": "image", "base64": b64, "mime_type": "image/jpeg", "filename": "tg_photo.jpg"}
    )
    await msg.edit_text(_safe_truncate(result.get("response", "Could not analyze.")))


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def _build_app(token: str) -> Application:
    app = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("tools",    cmd_tools))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("clear",    cmd_clear))
    app.add_handler(CallbackQueryHandler(handle_auth_button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def _error_handler(update, context):
        err = str(context.error)
        if "TimedOut" in err or "ConnectTimeout" in err:
            logger.debug(f"Telegram timeout (ignored): {err[:80]}")
        else:
            logger.warning(f"Telegram error: {err[:200]}")
    app.add_error_handler(_error_handler)

    return app


async def start_telegram_bot():
    global _tg_app
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    
    if not token or ":" not in token:
        logger.warning("TELEGRAM_BOT_TOKEN not set or invalid — Telegram bot disabled.")
        return

    if _tg_app:
        logger.info("Telegram bot is already running.")
        return

    try:
        _tg_app = _build_app(token)
        await _tg_app.initialize()
        await _tg_app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        await _tg_app.start()
        logger.info(f"✅ Telegram bot started — listening for @{(await _tg_app.bot.get_me()).username}")
    except httpx.ConnectError:
        logger.error("❌ Telegram Connection Error: Cannot reach api.telegram.org. This is likely a DNS/ISP block in your region.")
        _tg_app = None
    except Exception as e:
        logger.error(f"Telegram bot failed to start: {e}")
        _tg_app = None


async def stop_telegram_bot():
    global _tg_app
    if _tg_app:
        try:
            await _tg_app.updater.stop()
            await _tg_app.stop()
            await _tg_app.shutdown()
            logger.info("Telegram bot stopped.")
        except Exception as e:
            logger.warning(f"Telegram shutdown error: {e}")
        finally:
            _tg_app = None

async def restart_telegram_bot():
    """Stops and restarts the bot (called when settings are saved)."""
    logger.info("Restarting Telegram bot with new settings...")
    await stop_telegram_bot()
    await asyncio.sleep(1)
    await start_telegram_bot()
