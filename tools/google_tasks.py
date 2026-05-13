"""
Google Tasks tool — create, list, complete, delete tasks.
Uses OAuth2 with credentials.json for one-time auth.
Token saved to token.json — never needs re-auth after first time.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOOL_NAME = "google_tasks"
TOOL_DESCRIPTION = "Add, list, complete, delete tasks in Google Tasks — for future reminders and named to-do items"

logger = logging.getLogger("aether.tools.google_tasks")

def _get_service():
    from core.google_auth import get_service
    return get_service("tasks", "v1")


def _get_default_list_id() -> str:
    service = _get_service()
    result = service.tasklists().list().execute()
    lists = result.get("items", [])
    return lists[0]["id"] if lists else "@default"


def _parse_due_date(due_str: str) -> str | None:
    """
    Parse natural language due dates to RFC3339 format.
    Examples: "tomorrow", "tomorrow 9am", "next monday", "2026-04-10"
    """
    if not due_str:
        return None

    due_str = due_str.lower().strip()
    now = datetime.now()

    try:
        if "tomorrow" in due_str:
            base = now + timedelta(days=1)
            # Check for time
            if "am" in due_str or "pm" in due_str:
                import re
                match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', due_str)
                if match:
                    hour = int(match.group(1))
                    minute = int(match.group(2) or 0)
                    if match.group(3) == "pm" and hour != 12:
                        hour += 12
                    base = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                base = base.replace(hour=9, minute=0, second=0, microsecond=0)
            return base.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        if "next week" in due_str:
            base = now + timedelta(weeks=1)
            base = base.replace(hour=9, minute=0, second=0, microsecond=0)
            return base.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        if "monday" in due_str or "tuesday" in due_str or "wednesday" in due_str or \
           "thursday" in due_str or "friday" in due_str or "saturday" in due_str or "sunday" in due_str:
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for i, day in enumerate(days):
                if day in due_str:
                    days_ahead = (i - now.weekday()) % 7 or 7
                    base = now + timedelta(days=days_ahead)
                    base = base.replace(hour=9, minute=0, second=0, microsecond=0)
                    return base.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Try direct date parse
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"]:
            try:
                base = datetime.strptime(due_str, fmt)
                return base.strftime("%Y-%m-%dT09:00:00.000Z")
            except ValueError:
                pass

    except Exception as e:
        logger.warning(f"Could not parse due date '{due_str}': {e}")

    return None


async def run(**kwargs) -> str:
    """
    Actions:
    - add: add a new task (title, notes optional, due optional)
    - list: show all pending tasks
    - complete: mark task done (index — from list, 1-based)
    - delete: delete a task (index)
    - clear: delete all completed tasks
    """
    action = kwargs.get("action", "").lower().strip()
    title = kwargs.get("title") or kwargs.get("task") or kwargs.get("name") or ""
    notes = kwargs.get("notes") or kwargs.get("description") or kwargs.get("details") or ""
    due = kwargs.get("due") or kwargs.get("date") or kwargs.get("time") or ""
    
    try:
        index = int(kwargs.get("index")) if kwargs.get("index") is not None else None
    except (ValueError, TypeError):
        index = None
        
    task_id = kwargs.get("task_id") or kwargs.get("id") or ""

    try:
        # Run blocking Google API calls in thread to not block async event loop
        service = await asyncio.to_thread(_get_service)
        list_id = await asyncio.to_thread(_get_default_list_id)
    except Exception as e:
        return f"Google Tasks connection failed: {e}\nMake sure credentials.json is in the project root."

    # ── Add task ──────────────────────────────────────────────────────────────
    if action == "add":
        if not title:
            return "Bhai task ka title toh bata."
        task_body = {"title": title}
        if notes:
            task_body["notes"] = notes
        if due:
            due_date = _parse_due_date(due)
            if due_date:
                task_body["due"] = due_date

        try:
            result = await asyncio.to_thread(lambda: service.tasks().insert(tasklist=list_id, body=task_body).execute())
            due_str = f" (due: {due})" if due else ""
            return f"Task add ho gaya yaar: '{title}'{due_str}"
        except Exception as e:
            return f"Task add nahi hua: {e}"

    # ── List tasks ────────────────────────────────────────────────────────────
    elif action == "list":
        try:
            result = await asyncio.to_thread(lambda: service.tasks().list(
                tasklist=list_id,
                showCompleted=False,
                maxResults=20
            ).execute())
            tasks = result.get("items", [])
            if not tasks:
                return "Koi task nahi hai abhi. Sab clear hai yaar!"
            lines = []
            for i, t in enumerate(tasks, 1):
                title_str = t.get("title", "Untitled")
                due = t.get("due", "")
                due_str = ""
                if due:
                    due_dt = datetime.strptime(due[:10], "%Y-%m-%d")
                    due_str = f" — {due_dt.strftime('%d %b')}"
                lines.append(f"{i}. {title_str}{due_str}")
            return "Tera task list:\n" + "\n".join(lines)
        except Exception as e:
            return f"Tasks fetch nahi hue: {e}"

    # ── Complete task ─────────────────────────────────────────────────────────
    elif action == "complete":
        try:
            result = await asyncio.to_thread(lambda: service.tasks().list(
                tasklist=list_id, showCompleted=False, maxResults=20
            ).execute())
            tasks = result.get("items", [])
            if not tasks:
                return "Koi task nahi hai complete karne ke liye."
            if index is None or index < 1 or index > len(tasks):
                return f"Valid index bata — 1 se {len(tasks)} ke beech."
            task = tasks[index - 1]
            task["status"] = "completed"
            await asyncio.to_thread(lambda: service.tasks().update(
                tasklist=list_id, task=task["id"], body=task
            ).execute())
            return f"Done yaar! '{task['title']}' complete ho gaya."
        except Exception as e:
            return f"Complete nahi hua: {e}"

    # ── Delete task ───────────────────────────────────────────────────────────
    elif action == "delete":
        try:
            result = await asyncio.to_thread(lambda: service.tasks().list(
                tasklist=list_id, showCompleted=False, maxResults=20
            ).execute())
            tasks = result.get("items", [])
            if not tasks:
                return "Koi task nahi hai delete karne ke liye."
            if index is None or index < 1 or index > len(tasks):
                return f"Valid index bata — 1 se {len(tasks)} ke beech."
            task = tasks[index - 1]
            await asyncio.to_thread(lambda: service.tasks().delete(
                tasklist=list_id, task=task["id"]
            ).execute())
            return f"Delete ho gaya: '{task['title']}'"
        except Exception as e:
            return f"Delete nahi hua: {e}"

    # ── Clear completed ───────────────────────────────────────────────────────
    elif action == "clear":
        try:
            await asyncio.to_thread(lambda: service.tasks().clear(tasklist=list_id).execute())
            return "Saare completed tasks clear ho gaye yaar!"
        except Exception as e:
            return f"Clear nahi hua: {e}"

    else:
        return "Available actions: add, list, complete, delete, clear"
