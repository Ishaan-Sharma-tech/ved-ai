"""
Daily Briefing Tool — Ishaan's morning command center.
Aggregates emails, tasks, notes, and weather into one clean briefing.
"""

import asyncio
import logging
from datetime import datetime
from core.corporate.utils import _resilient_chat

TOOL_NAME = "daily_briefing"
TOOL_DESCRIPTION = "Generate a smart daily briefing: unread emails, pending tasks, notes, and weather — delivered as one clean summary."

logger = logging.getLogger("aether.tools.daily_briefing")

# WebSocket push callbacks — set by main.py so briefings can push to UI
_push_callbacks: dict = {}

def set_push_callback(fn, session_id: str = "global"):
    """Register the WebSocket push function for a specific session."""
    if fn:
        _push_callbacks[session_id] = fn
    elif session_id in _push_callbacks:
        del _push_callbacks[session_id]

async def _safe_fetch(coro, label: str, fallback: str = "Unavailable.") -> str:
    """Run a coroutine safely, return fallback on any error."""
    try:
        result = await asyncio.wait_for(coro, timeout=12.0)
        return str(result) if result else fallback
    except asyncio.TimeoutError:
        logger.warning(f"[briefing] {label} timed out.")
        return f"{label}: Timed out."
    except Exception as e:
        logger.warning(f"[briefing] {label} error: {e}")
        return f"{label}: Error ({e})"

async def run(**kwargs) -> str:
    """
    Compile and deliver a smart daily briefing.
    """
    time_of_day = kwargs.get("time_of_day", "morning")
    auto = kwargs.get("auto", False)

    from tool_runtime.loader import TOOL_REGISTRY

    now = datetime.now()
    date_str = now.strftime("%A, %d %B %Y — %I:%M %p")
    greeting_map = {
        "morning": "Good Morning, Boss!",
        "evening": "Good Evening, Sir!",
        "night": "Night briefing ready, Boss!"
    }
    greeting = greeting_map.get(time_of_day.lower(), "Here's your briefing, Boss!")

    logger.info(f"[briefing] Generating {time_of_day} briefing...")

    # Fetch all intel in parallel
    email_task    = _safe_fetch(TOOL_REGISTRY["gmail"](action="inbox"),       "Emails")
    tasks_task    = _safe_fetch(TOOL_REGISTRY["google_tasks"](action="list"), "Tasks")
    notes_task    = _safe_fetch(TOOL_REGISTRY["notes"](action="list"),        "Notes")
    from core.prompt_builder import USER_NAME, USER_BIO, USER_LOCATION
    
    weather_query = f"current weather in {USER_LOCATION} today"
    weather_task  = _safe_fetch(
        TOOL_REGISTRY["web_search"](query=weather_query),
        "Weather"
    )

    emails, tasks, notes, weather = await asyncio.gather(
        email_task, tasks_task, notes_task, weather_task
    )

    raw_intel = f"""
DATE: {date_str}
EMAILS (Inbox):
{emails[:800]}
PENDING TASKS:
{tasks[:600]}
RECENT NOTES:
{notes[:400]}
WEATHER:
{weather[:300]}
""".strip()

    system_prompt = f"""You are Ved, {USER_NAME}'s elite AI assistant. It is {time_of_day}.
Generate a crisp, powerful daily briefing from the raw intel below.
Format it as:
1. A one-line greeting with date.
2. 📧 Email summary: unread count and 2-3 key subjects.
3. ✅ Tasks: list pending tasks with priority.
4. 📝 Notes: recent note highlights.
5. 🌤️ Weather: one clean line based on {USER_LOCATION}.
6. A sharp motivational closing line tailored to {USER_NAME} ({USER_BIO}).
Keep the whole response under 200 words."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": raw_intel}
    ]

    try:
        briefing = await _resilient_chat(messages, "llama-3.3-70b-versatile", role="worker")
    except Exception as e:
        briefing = f"{greeting}\n\n{raw_intel}"
        logger.error(f"[briefing] LLM synthesis failed: {e}")

    final = f"🌅 **{greeting}**\n\n{briefing}"

    if auto and _push_callbacks:
        for sid, cb in _push_callbacks.items():
            try:
                await cb(final)
            except Exception as e:
                logger.warning(f"[briefing] Push failed for {sid}: {e}")
    
    return final
