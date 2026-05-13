"""
Orchestrator — Corporate Swarm Edition.
Main message pipeline with hierarchical routing and 429 auto-recovery.
"""

import logging
import base64
import shlex
import asyncio
import uuid

from core.memory import get_recent, save_turn, search_memory, get_all_facts
from core.prompt_builder import build_prompt
from core.privacy import check_message, sanitize_for_api
from core.task_classifier import classify, get_cached_search, set_search_cache
from core.tool_schemas import validate_and_fix
from core.openrouter_vision import analyze_image, analyze_document
from core.knowledge_graph import extract_and_inject, get_context_from_kg

# New Corporate Imports
from core.swarm import SwarmOrchestrator, get_active_swarms, cancel_swarm
from core.corporate.freelance import FreelanceAgent
from core.corporate.utils import _resilient_chat
from core.corporate.tool_utils import _safe_run_tool, _is_destructive, PENDING_AUTH
from tool_runtime.loader import TOOL_REGISTRY, run_tool, load_manifest

logger = logging.getLogger("aether.orchestrator")

def _ensure_string(content) -> str:
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text") or "[image]"
    if not isinstance(content, str):
        return str(content)
    return content

def _clean_history(messages: list) -> list:
    return [{**m, "content": _ensure_string(m.get("content", ""))} for m in messages]

def _parse_tool_kwargs(args_str: str) -> dict:
    kwargs = {}
    if not args_str: return kwargs
    try:
        tokens = shlex.split(args_str)
    except Exception:
        tokens = args_str.split()
    last_key = None
    for token in tokens:
        if "=" in token:
            k, v = token.split("=", 1)
            last_key = k.strip()
            kwargs[last_key] = v.strip()
        elif last_key:
            kwargs[last_key] = kwargs[last_key] + " " + token
    return kwargs

async def _fetch_memory(session_id: str, content: str) -> tuple:
    try:
        recent, memory_hits = await asyncio.gather(
            get_recent(session_id, limit=15),
            search_memory(content, limit=3),
            return_exceptions=True
        )
        kg_facts_list = get_context_from_kg(content)
        facts = {f"Fact {i}": text for i, text in enumerate(kg_facts_list)}
        if isinstance(recent, Exception): recent = []
        if isinstance(memory_hits, Exception): memory_hits = []
        return recent, facts, memory_hits
    except Exception as e:
        logger.error(f"Memory fetch error: {e}")
        return [], {}, []

async def _stream_text(text: str, on_chunk) -> None:
    if not on_chunk or not text: return
    chunk_size = 400
    for i in range(0, len(text), chunk_size):
        await on_chunk(text[i:i+chunk_size])

async def process_message(
    content: str,
    session_id: str,
    on_chunk=None,
    file_data: dict | None = None,
    auth_reply: dict | None = None
) -> dict:
    global PENDING_AUTH
    
    text_lower = content.lower().strip()
    if not auth_reply and session_id in PENDING_AUTH and text_lower in ["continue", "yes", "proceed", "do it", "approve"]:
        auth_reply = {"auth_id": PENDING_AUTH[session_id]["auth_id"], "confirm": True}
    elif not auth_reply and session_id in PENDING_AUTH and text_lower in ["no", "cancel", "stop", "abort"]:
        auth_reply = {"auth_id": PENDING_AUTH[session_id]["auth_id"], "confirm": False}

    if auth_reply:
        auth_id, confirm = auth_reply.get("auth_id"), auth_reply.get("confirm", False)
        pending = PENDING_AUTH.get(session_id)
        if pending and pending["auth_id"] == auth_id:
            del PENDING_AUTH[session_id]
            if confirm:
                result = await _safe_run_tool(pending["tool"], pending["args"])
                await _stream_text(f"Action executed: {result}", on_chunk)
                return {"response": result, "model": "tool_runtime", "task_type": "tool_call"}
            else:
                msg = "Action canceled securely by Admin."
                await _stream_text(msg, on_chunk)
                return {"response": msg, "model": "local", "task_type": "tool_call"}

    # 1. Privacy check
    privacy = check_message(content)
    if not privacy["safe"]:
        msg = privacy["message"]
        await _stream_text(msg, on_chunk)
        return {"response": msg, "model": "local", "task_type": "privacy_block"}
    scrubbed = privacy["scrubbed"]

    # 2. KG Background Injection
    if scrubbed: asyncio.create_task(extract_and_inject(scrubbed))

    # 3. Vision Engine
    if file_data and "base64" in file_data:
        try:
            if file_data.get("type") == "image":
                response = await analyze_image(scrubbed, file_data["base64"], file_data["mime_type"])
            else:
                decoded = base64.b64decode(file_data["base64"]).decode("utf-8", errors="replace")
                response = await analyze_document(scrubbed, decoded)
            await save_turn(session_id, "user", content, "vision")
            await save_turn(session_id, "assistant", response, "vision", "vision_engine")
            await _stream_text(response, on_chunk)
            return {"response": response, "model": "vision_engine", "task_type": "vision"}
        except Exception as e:
            await _stream_text(f"Vision error: {e}", on_chunk)
            return {"response": str(e), "model": "error", "task_type": "vision"}

    # 4. Meta commands
    if lower := scrubbed.lower().strip():
        if lower in ["list tools", "show tools"]:
            resp = "Tools: " + ", ".join(TOOL_REGISTRY.keys())
            await _stream_text(resp, on_chunk); return {"response": resp, "task_type": "meta"}
        if lower in ["task status", "active tasks"]:
            swarms = get_active_swarms()
            resp = "No active tasks." if not swarms else "\n".join(f"🐝 `{s}`: {i['goal']}" for s, i in swarms.items())
            await _stream_text(resp, on_chunk); return {"response": resp, "task_type": "meta"}
        if lower.startswith("cancel swarm "):
            resp = cancel_swarm(lower.replace("cancel swarm ", "").strip())
            await _stream_text(resp, on_chunk); return {"response": resp, "task_type": "meta"}

    # 5. Classifier + Memory
    manifest = load_manifest()
    classification, (recent, facts, memory_hits) = await asyncio.gather(
        classify(scrubbed, manifest),
        _fetch_memory(session_id, scrubbed)
    )

    # 6. Corporate Swarm (Multi-Step / Complex)
    if classification.get("type") in ["swarm", "multi_step"]:
        goal = classification.get("goal", scrubbed)
        swarm_id = str(uuid.uuid4())[:8]
        swarm_msg = f"🏢 **Corporate Swarm Activated (ID: `{swarm_id}`)**\nAssigning departments to solve: *{goal}*"
        await _stream_text(swarm_msg, on_chunk)
        asyncio.create_task(SwarmOrchestrator().run(goal, session_id, swarm_id))
        return {"response": swarm_msg, "model": "swarm", "task_type": "swarm"}

    # 7. Tool Call (Single)
    if classification.get("type") == "tool_call":
        tool, args = classification.get("tool"), classification.get("args", {})
        if _is_destructive(tool, args):
            auth_id = str(uuid.uuid4())
            PENDING_AUTH[session_id] = {"auth_id": auth_id, "tool": tool, "args": args}
            msg = f"⚠️ Security Guardrail: Awaiting approval for `{tool}`."
            await _stream_text(msg, on_chunk)
            return {"response": msg, "task_type": "auth_request"}
        
        result = await _safe_run_tool(tool, args)
        if tool == "web_search":
            # Natural LLM pass for search
            system_prompt = build_prompt(memory_context=memory_hits, facts=facts)
            messages = [{"role": "system", "content": system_prompt}] + _clean_history(recent)
            messages.append({"role": "user", "content": f"{scrubbed}\n\nSearch: {result}"})
            response = await _resilient_chat(messages, "llama-3.1-8b-instant", role="freelance")
            await _stream_text(response, on_chunk)
            await save_turn(session_id, "assistant", response, "web_search")
            return {"response": response, "task_type": "web_search"}
        
        await _stream_text(result, on_chunk)
        await save_turn(session_id, "assistant", result, "tool_call")
        return {"response": result, "task_type": "tool_call"}

    # 8. Freelance Agent (Chat-Only / Basic)
    system_prompt = build_prompt(memory_context=memory_hits, facts=facts)
    messages = [{"role": "system", "content": system_prompt}] + _clean_history(recent)
    messages.append({"role": "user", "content": scrubbed})
    
    response = await FreelanceAgent().run_fast_task(scrubbed, session_id, messages)
    await _stream_text(response, on_chunk)
    return {"response": response, "model": "freelance", "task_type": "chat"}
