"""
File manager tool — create, read, edit files inside the workspace sandbox.
Ved cannot access anything outside this sandbox.
"""

import os
import logging
from pathlib import Path
from core.config import get_workspace

TOOL_NAME = "file_manager"
TOOL_DESCRIPTION = "Create, read, edit, list, delete files inside your workspace"

logger = logging.getLogger("aether.tools.file_manager")

def _safe_path(relative: str) -> Path | None:
    try:
        ws = get_workspace()
        target = (ws / relative).resolve()
        if not str(target).startswith(str(ws.resolve())):
            logger.warning(f"Path escape attempt blocked: {relative}")
            return None
        return target
    except Exception:
        return None

def _ensure_workspace():
    get_workspace().mkdir(parents=True, exist_ok=True)


async def run(**kwargs) -> str:
    _ensure_workspace()
    action = kwargs.get("action", "").lower().strip()
    path = kwargs.get("path") or kwargs.get("filename") or kwargs.get("file") or kwargs.get("name") or ""
    content = kwargs.get("content") or kwargs.get("text") or kwargs.get("body") or ""
    pattern = kwargs.get("pattern") or kwargs.get("query") or kwargs.get("search") or ""
    replacement = kwargs.get("replacement") or kwargs.get("replace_with") or ""

    # ── Create ────────────────────────────────────────────────────────────────
    if action == "create":
        if not path:
            return "Specify file path relative to workspace."
        target = _safe_path(path)
        if not target:
            return "Access denied: cannot write outside workspace"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"maine aapke workspace mein file create kar di hai: {path}"

    # ── Read ──────────────────────────────────────────────────────────────────
    elif action == "read":
        if not path:
            return "Specify file path."
        target = _safe_path(path)
        if not target or not target.exists():
            return f"File not found: {path}"
        try:
            text = target.read_text(encoding="utf-8")
            return f"--- {path} ---\n{text}"
        except Exception as e:
            return f"Read error: {e}"

    # ── Edit (find & replace) ─────────────────────────────────────────────────
    elif action == "edit":
        if not path or not pattern:
            return "Specify path and pattern to find."
        target = _safe_path(path)
        if not target or not target.exists():
            return f"File not found: {path}"
        text = target.read_text(encoding="utf-8")
        if pattern not in text:
            return f"Pattern not found in {path}: '{pattern}'"
        updated = text.replace(pattern, replacement, 1)
        target.write_text(updated, encoding="utf-8")
        return f"Edited {path} — replaced '{pattern[:40]}'"

    # ── Append ────────────────────────────────────────────────────────────────
    elif action == "append":
        if not path:
            return "Specify file path."
        target = _safe_path(path)
        if not target:
            return "Access denied."
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} chars to {path}"

    # ── Delete ────────────────────────────────────────────────────────────────
    elif action == "delete":
        if not path:
            return "Specify file path."
        target = _safe_path(path)
        if not target or not target.exists():
            return f"File not found: {path}"
        target.unlink()
        return f"Deleted: {path}"

    # ── List ──────────────────────────────────────────────────────────────────
    elif action == "list":
        base = _safe_path(path) if path else get_workspace()
        if not base or not base.exists():
            return f"Folder not found: {path or 'workspace'}"
        items = []
        for item in sorted(base.iterdir()):
            size = f"{item.stat().st_size}B" if item.is_file() else "DIR"
            items.append(f"{'📁' if item.is_dir() else '📄'} {item.name} ({size})")
        if not items:
            return f"Empty workspace."
        return f"Contents of {base}:\n" + "\n".join(items)

    # ── Mkdir ─────────────────────────────────────────────────────────────────
    elif action == "mkdir":
        if not path:
            return "Specify folder name."
        target = _safe_path(path)
        if not target:
            return "Access denied."
        target.mkdir(parents=True, exist_ok=True)
        return f"Created folder: {target}"

    # ── Search ────────────────────────────────────────────────────────────────
    elif action == "search":
        if not pattern:
            return "Specify search pattern."
        results = []
        for fpath in get_workspace().rglob("*"):
            if fpath.is_file():
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                    if pattern.lower() in text.lower():
                        lines = [
                            f"  line {i+1}: {line.strip()}"
                            for i, line in enumerate(text.splitlines())
                            if pattern.lower() in line.lower()
                        ]
                        results.append(f"{fpath.relative_to(get_workspace())}:\n" + "\n".join(lines[:3]))
                except Exception:
                    pass
        if not results:
            return f"No files contain: '{pattern}'"
        return f"Found in {len(results)} file(s):\n" + "\n\n".join(results)

    else:
        return (
            f"Unknown action: '{action}'. "
            "Available: create, read, edit, append, delete, list, mkdir, search"
        )
