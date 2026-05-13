"""
Task classifier — fast pre-filter + LLM fallback.
Post-validated against tool schemas to guarantee correct args.
"""
import os
import re
import json
import time
import logging
import httpx
from groq import AsyncGroq
from core.tool_schemas import validate_and_fix

logger = logging.getLogger("aether.classifier")
_client_cache: dict = {}  # key -> client
CLASSIFIER_MODEL = "llama-3.1-8b-instant"

def get_client() -> AsyncGroq:
    """Get a Groq client from the Corporate Vault universal pool."""
    from core.corporate.vault import GROQ_VAULT
    key = GROQ_VAULT.get_universal_key()
    if not key:
        raise ValueError("No GROQ API key found in Vault.")
    if key not in _client_cache:
        _client_cache[key] = AsyncGroq(api_key=key, timeout=15.0)
    return _client_cache[key]

# ── Search cache ──────────────────────────────────────────────────────────────
_search_cache: dict = {}
CACHE_TTL = 300

def get_cached_search(query: str) -> str | None:
    key = query.lower().strip()
    if key in _search_cache:
        result, ts = _search_cache[key]
        if time.time() - ts < CACHE_TTL:
            return result
        del _search_cache[key]
    return None

def set_search_cache(query: str, result: str):
    _search_cache[query.lower().strip()] = (result, time.time())

# ── Session memory cache ──────────────────────────────────────────────────────
_session_cache: dict = {}  # session_id -> {"recent": [...], "ts": float}
SESSION_CACHE_TTL = 30  # 30 seconds

def get_cached_session(session_id: str) -> dict | None:
    if session_id in _session_cache:
        entry = _session_cache[session_id]
        if time.time() - entry["ts"] < SESSION_CACHE_TTL:
            return entry
    return None

def set_session_cache(session_id: str, recent: list, facts: dict):
    _session_cache[session_id] = {"recent": recent, "facts": facts, "ts": time.time()}

def invalidate_session_cache(session_id: str):
    _session_cache.pop(session_id, None)

# ── Pre-filter patterns ───────────────────────────────────────────────────────
CHAT_ONLY = re.compile(
    r'^(hello|hi|hey|hii|namaste|namaskar|yo|sup|helo|'
    r'thanks?|thank you|shukriya|dhanyawad|'
    r'bye|goodbye|alvida|'
    r'ok|okay|haan|nahi|yes|no|fine|good|'
    r'what is [a-zA-Z ]{2,25}\??|'
    r'define [a-zA-Z ]{2,20}|'
    r'who is [a-zA-Z ]{2,25}|'
    r'how (does|do|is|are) [a-zA-Z ]{2,30}|'
    r'explain [a-zA-Z ]{2,30}|'
    r'(write|make|generate) (a |an )?(poem|story|essay|joke))[\s!?.]*$',
    re.IGNORECASE
)

def pre_filter(message: str) -> dict | None:
    lower = message.lower().strip()
    if CHAT_ONLY.match(lower):
        logger.info(f"Pre-filter: chat — '{message[:40]}'")
        return {"type": "chat"}
    return None


def _build_prompt(tools: dict) -> str:
    tool_list = "\n".join(f'- {n}: {i.get("description","")[:80]}' for n, i in tools.items())
    return f"""Task classifier for Ved AI assistant.

Tools:
{tool_list}

STRICT RULES — use EXACT action names:
- gmail actions: inbox | unread | search | send | read | draft | read_thread
- notes actions: add | list | read | search | delete | tag
- file_manager actions: create | read | edit | append | delete | list | mkdir | search | rename | recent | info
- scheduler actions: remind | repeat | list | cancel
- google_tasks actions: add | list | complete | delete | clear
- drive actions: list | search | read | storage | create | download | upload
- system_control actions: open | sysinfo | volume | brightness | screenshot | lock | empty_trash | mute_mic | unmute_mic
- meta_developer actions: list | read | create | delete
- workspace_manager actions: enable_focus | disable_focus
- daily_briefing: use time_of_day= parameter (morning | evening | night)


IMPORTANT — MULTI-STEP DETECTION:
If the user's request clearly requires 2 or more DIFFERENT tools executed in sequence (e.g. "search X AND save it", "research Y, write report, email it"), return:
{{"type": "multi_step", "goal": "<original user message>"}}

IMPORTANT — SWARM DETECTION:
If the user's request involves PARALLEL, INDEPENDENT tasks that require different domains (e.g., retrieving emails AND searching the web AND reading files simultaneously), return:
{{"type": "swarm", "goal": "<original user message>"}}

Do NOT try to pick just one tool for multi-step or swarm requests.

Return ONLY valid JSON. No markdown. No conversational text.
If a user request cannot be strictly fulfilled by these tools, just return {{"type": "chat"}} and DO NOT EXPLAIN IT.
IMPORTANT: YOU CAN ONLY OUTPUT TOOLS FROM THE PROVIDED LIST. NEVER hallucinate a tool name that is not in the list. If the user asks to create, make, or build a tool, ALWAYS use "meta_developer" and pass the full request as the "prompt" argument.

Examples:
"weather Mumbai" → {{"type":"tool_call","tool":"web_search","args":{{"query":"current weather Mumbai"}}}}
"read my emails" → {{"type":"tool_call","tool":"gmail","args":{{"action":"inbox"}}}}
"save note study physics" → {{"type":"tool_call","tool":"notes","args":{{"action":"add","content":"study physics"}}}}
"create a tool to check crypto prices" → {{"type":"tool_call","tool":"meta_developer","args":{{"action":"create","name":"crypto_tracker","prompt":"create a tool to check crypto prices"}}}}
"what is Python" → {{"type":"chat"}}
"explain recursion" → {{"type":"chat"}}"""



async def classify(message: str, available_tools: dict) -> dict:
    if not available_tools:
        return {"type": "chat"}

    pre = pre_filter(message)
    if pre:
        return pre

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": _build_prompt(available_tools)},
                {"role": "user", "content": message}
            ],
            max_tokens=600,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end+1]
        else:
            raise json.JSONDecodeError("No JSON braces found", raw, 0)
        
        result = json.loads(raw)

        # Post-validate and fix args against tool schema
        if result.get("type") == "tool_call":
            tool = result.get("tool", "")
            args = result.get("args", {})
            result["args"] = validate_and_fix(tool, args)

        logger.info(f"Classified '{message[:50]}' → {result}")
        return result

    except json.JSONDecodeError:
        logger.warning(f"Classifier bad JSON for: {message[:40]}")
        return {"type": "chat"}
    except Exception as e:
        logger.warning(f"Classifier error: {e}")
        return {"type": "chat"}
