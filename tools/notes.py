"""
Notes tool — quick personal notes with tags, search, export.
Stored in workspace/notes/
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from core.config import get_workspace

TOOL_NAME = "notes"
TOOL_DESCRIPTION = "Create, read, search and manage personal notes with tags"

logger = logging.getLogger("aether.tools.notes")

def _ensure_dir() -> Path:
    ndir = get_workspace() / "notes"
    ndir.mkdir(parents=True, exist_ok=True)
    return ndir


def _load_index(ndir) -> list:
    try:
        index_file = ndir / ".index.json"
        if index_file.exists():
            return json.loads(index_file.read_text())
    except Exception:
        pass
    return []


def _save_index(ndir, index: list):
    index_file = ndir / ".index.json"
    index_file.write_text(json.dumps(index, indent=2))


def _next_id(index: list) -> int:
    return max((n["id"] for n in index), default=0) + 1


async def run(**kwargs) -> str:
    action = kwargs.get("action", "").lower().strip()
    content = kwargs.get("content") or kwargs.get("text") or kwargs.get("body") or ""
    tags = kwargs.get("tags") or kwargs.get("tag") or ""
    query = kwargs.get("query") or kwargs.get("search") or ""
    try:
        raw_id = kwargs.get("note_id") or kwargs.get("id")
        note_id = int(raw_id) if raw_id is not None else None
    except (ValueError, TypeError):
        note_id = None
    title = kwargs.get("title") or kwargs.get("name") or ""
    
    ndir = _ensure_dir()

    # ── Add note ───────────────────────────────────────────────────────────────
    if action == "add":
        if not content:
            return "Note ka content bata yaar."
        index = _load_index(ndir)
        nid = _next_id(index)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        now = datetime.now()
        note = {
            "id": nid,
            "title": title or content[:40],
            "content": content,
            "tags": tag_list,
            "created": now.strftime("%d %b %Y %I:%M %p"),
            "file": f"note_{nid}.txt"
        }
        # Save to file
        (ndir / note["file"]).write_text(content, encoding="utf-8")
        index.append(note)
        _save_index(ndir, index)
        tag_str = f" [tags: {', '.join(tag_list)}]" if tag_list else ""
        return f"Note saved! ID: {nid}{tag_str}"

    # ── List notes ─────────────────────────────────────────────────────────────
    elif action == "list":
        index = _load_index(ndir)
        if not index:
            return "Koi note nahi hai abhi. Kuch likhte hain?"
        lines = []
        for n in index[-10:]:
            tag_str = f" [{', '.join(n['tags'])}]" if n.get("tags") else ""
            lines.append(f"{n['id']}. {n['title']}{tag_str} — {n['created']}")
        return "Teri notes:\n" + "\n".join(reversed(lines))

    # ── Read note ──────────────────────────────────────────────────────────────
    elif action == "read":
        if note_id is None:
            return "Note ID bata."
        index = _load_index(ndir)
        note = next((n for n in index if n["id"] == note_id), None)
        if not note:
            return f"Note #{note_id} nahi mili."
        fpath = ndir / note["file"]
        content_text = fpath.read_text(encoding="utf-8") if fpath.exists() else note.get("content", "")
        tag_str = f"\nTags: {', '.join(note['tags'])}" if note.get("tags") else ""
        return f"Note #{note_id}: {note['title']}\n{note['created']}{tag_str}\n\n{content_text}"

    # ── Search notes ───────────────────────────────────────────────────────────
    elif action == "search":
        if not query:
            return "Search query bata."
        index = _load_index(ndir)
        results = []
        ql = query.lower()
        for n in index:
            if ql in n["title"].lower() or ql in n["content"].lower() or \
               any(ql in t.lower() for t in n.get("tags", [])):
                results.append(n)
        if not results:
            return f"'{query}' wali koi note nahi mili."
        lines = [f"{n['id']}. {n['title']} — {n['created']}" for n in results]
        return f"Search results for '{query}':\n" + "\n".join(lines)

    # ── Delete note ────────────────────────────────────────────────────────────
    elif action == "delete":
        if note_id is None:
            return "Note ID bata."
        index = _load_index(ndir)
        note = next((n for n in index if n["id"] == note_id), None)
        if not note:
            return f"Note #{note_id} nahi mili."
        fpath = ndir / note["file"]
        if fpath.exists():
            fpath.unlink()
        index = [n for n in index if n["id"] != note_id]
        _save_index(ndir, index)
        return f"Note #{note_id} delete ho gayi: '{note['title']}'"

    # ── Tag filter ─────────────────────────────────────────────────────────────
    elif action == "tag":
        if not tags:
            return "Tag name bata."
        index = _load_index(ndir)
        results = [n for n in index if tags.lower() in [t.lower() for t in n.get("tags", [])]]
        if not results:
            return f"'{tags}' tag wali koi note nahi."
        lines = [f"{n['id']}. {n['title']} — {n['created']}" for n in results]
        return f"Notes with tag '{tags}':\n" + "\n".join(lines)

    else:
        return "Available actions: add, list, read, search, delete, tag"
