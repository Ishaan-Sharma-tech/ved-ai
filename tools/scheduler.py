"""
Scheduler tool — schedule one-time and recurring tasks.
"""

import re
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

TOOL_NAME = "scheduler"
TOOL_DESCRIPTION = "Schedule reminders and recurring tasks — one-time or repeating"

logger = logging.getLogger("aether.tools.scheduler")

_scheduler: AsyncIOScheduler | None = None
_jobs: dict = {}
_push_callbacks: dict = {} # session_id -> callback

def set_push_callback(fn, session_id: str = "global"):
    """Register the WebSocket push function for a specific session."""
    if fn:
        _push_callbacks[session_id] = fn
    elif session_id in _push_callbacks:
        del _push_callbacks[session_id]

def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logger.info("APScheduler started")
    return _scheduler


async def _reminder_callback(message: str, session_id: str = "global"):
    logger.info(f"[REMINDER] {message} (Session: {session_id})")
    # Push to UI if callback exists
    cb = _push_callbacks.get(session_id)
    if cb:
        try:
            await cb(f"🔔 **Reminder Boss:** {message}")
        except Exception as e:
            logger.warning(f"Reminder push failed: {e}")
    print(f"\n🔔 Ved Reminder: {message}\n")


async def run(**kwargs) -> str:
    """
    Actions: remind, repeat, list, cancel, cancel_all
    """
    scheduler = get_scheduler()
    session_id = kwargs.get("session_id", "global")
    action = kwargs.get("action", "").lower().strip()
    message = kwargs.get("message") or kwargs.get("task") or kwargs.get("reminder") or ""
    when = str(kwargs.get("when") or kwargs.get("time") or kwargs.get("date") or "")
    interval = str(kwargs.get("interval") or kwargs.get("repeat") or "")
    job_id = kwargs.get("job_id") or kwargs.get("id") or ""

    # Absorb extra kwargs into when/interval if they weren't quoted properly
    extra_keys = set(kwargs.keys()) - {"action", "message", "when", "time", "date", "interval", "repeat", "job_id", "id", "task", "reminder"}
    extra = " ".join(str(kwargs[k]) for k in extra_keys if kwargs[k])
    
    if extra:
        if action == "remind" and when:
            when = f"{when} {extra}".strip()
        elif action == "repeat" and interval:
            interval = f"{interval} {extra}".strip()

    if action == "remind":
        if not message:
            return "Specify a reminder message."
        if not when:
            return "Specify when — e.g. 'in 5 minutes', '10:30', or '2026-04-01 09:00'"
        trigger = _parse_when(when)
        if isinstance(trigger, str):
            return trigger
        jid = f"remind_{len(_jobs)+1}"
        scheduler.add_job(_reminder_callback, trigger=trigger, args=[message, session_id], id=jid, replace_existing=True)
        _jobs[jid] = f"[one-time] {message} — {when}"
        return f"Reminder set: '{message}' at {when} (ID: {jid})"

    elif action == "repeat":
        if not message or not interval:
            return "Specify message and interval."
        trigger = _parse_interval(interval)
        if isinstance(trigger, str):
            return trigger
        jid = f"repeat_{len(_jobs)+1}"
        scheduler.add_job(_reminder_callback, trigger=trigger, args=[message, session_id], id=jid, replace_existing=True)
        _jobs[jid] = f"[recurring] {message} — {interval}"
        return f"Recurring reminder set: '{message}' {interval} (ID: {jid})"

    elif action == "list":
        if not _jobs:
            return "No scheduled jobs."
        return "Scheduled jobs:\n" + "\n".join(f"- {jid}: {desc}" for jid, desc in _jobs.items())

    elif action == "cancel":
        if not job_id:
            return "Specify job_id."
        try:
            scheduler.remove_job(job_id)
            desc = _jobs.pop(job_id, job_id)
            return f"Cancelled: {desc}"
        except Exception as e:
            return f"Could not cancel '{job_id}': {e}"

    elif action == "cancel_all":
        scheduler.remove_all_jobs()
        _jobs.clear()
        return "All jobs cancelled."

    else:
        return "Available actions: remind, repeat, list, cancel, cancel_all"


def _parse_when(when: str):
    when = when.strip().lower()
    now = datetime.now()
    try:
        m = re.match(r'in\s+(\d+)\s+(minute|minutes|hour|hours|second|seconds)', when)
        if m:
            amount = int(m.group(1))
            unit = m.group(2).rstrip("s") + "s"
            return DateTrigger(run_date=now + timedelta(**{unit: amount}))

        m = re.match(r'(\d{1,2}):(\d{2})', when)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            run_date = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if run_date < now:
                run_date += timedelta(days=1)
            return DateTrigger(run_date=run_date)

        run_date = datetime.strptime(when, "%Y-%m-%d %H:%M")
        return DateTrigger(run_date=run_date)
    except Exception as e:
        return f"Could not parse time '{when}'. Use: 'in 5 minutes', '10:30', '2026-04-01 09:00'"


def _parse_interval(interval: str):
    interval = interval.strip().lower()
    try:
        m = re.match(r'every\s+(\d+)\s+(minute|minutes|hour|hours)', interval)
        if m:
            amount = int(m.group(1))
            unit = m.group(2).rstrip("s") + "s"
            return IntervalTrigger(**{unit: amount})

        m = re.match(r'daily\s+at\s+(\d{1,2}):(\d{2})', interval)
        if m:
            return CronTrigger(hour=int(m.group(1)), minute=int(m.group(2)))

        if interval in ["daily", "every day"]:
            return IntervalTrigger(days=1)
        if interval in ["hourly", "every hour"]:
            return IntervalTrigger(hours=1)

        return f"Could not parse interval '{interval}'. Use: 'every 30 minutes', 'daily at 9:00'"
    except Exception as e:
        return f"Interval parse error: {e}"
