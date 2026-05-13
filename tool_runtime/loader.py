import importlib
import importlib.util
import sys
import os
import json
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from pathlib import Path

logger = logging.getLogger("aether.tool_runtime")

# Get absolute project root (one level up from tool_runtime folder)
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
TOOLS_DIR = str(PROJECT_ROOT / "tools")
MANIFEST_PATH = str(PROJECT_ROOT / "tools" / "manifest.json")

# Live registry of loaded tools  {name: callable}
TOOL_REGISTRY: dict = {}

def load_manifest() -> dict:
    try:
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

def save_manifest(data: dict):
    with open(MANIFEST_PATH, "w") as f:
        json.dump(data, f, indent=2)

def load_tool_module(filepath: str) -> bool:
    """Dynamically load or reload a tool module from filepath."""
    name = os.path.splitext(os.path.basename(filepath))[0]
    if name.startswith("_") or name == "manifest":
        return False
    try:
        spec = importlib.util.spec_from_file_location(f"tools.{name}", filepath)
        module = importlib.util.module_from_spec(spec)
        # Remove old version from sys.modules if present
        sys.modules.pop(f"tools.{name}", None)
        spec.loader.exec_module(module)
        sys.modules[f"tools.{name}"] = module

        # Each tool module must expose: TOOL_NAME, TOOL_DESCRIPTION, run()
        if hasattr(module, "run") and hasattr(module, "TOOL_NAME"):
            TOOL_REGISTRY[module.TOOL_NAME] = module.run
            manifest = load_manifest()
            manifest[module.TOOL_NAME] = {
                "description": getattr(module, "TOOL_DESCRIPTION", ""),
                "file": os.path.basename(filepath),
                "loaded_at": time.time(),
            }
            save_manifest(manifest)
            logger.info(f"[tool_runtime] Loaded tool: {module.TOOL_NAME}")
            return True
        else:
            logger.warning(f"[tool_runtime] {name}.py missing TOOL_NAME or run() — skipped")
            return False
    except Exception as e:
        logger.error(f"[tool_runtime] Failed to load {name}: {e}")
        return False

def load_all_tools():
    """Load all .py files in /tools on startup."""
    os.makedirs(TOOLS_DIR, exist_ok=True)
    if not os.path.exists(MANIFEST_PATH):
        save_manifest({})
    for fname in os.listdir(TOOLS_DIR):
        if fname.endswith(".py") and not fname.startswith("_"):
            load_tool_module(os.path.join(TOOLS_DIR, fname))

async def run_tool(name: str, **kwargs) -> str:
    """Call a registered tool by name."""
    if name not in TOOL_REGISTRY:
        return f"Tool '{name}' not found. Available: {list(TOOL_REGISTRY.keys())}"
    try:
        result = await TOOL_REGISTRY[name](**kwargs)
        return str(result)
    except Exception as e:
        return f"Tool '{name}' error: {e}"

def write_tool(filename: str, code: str) -> str:
    """
    Ved calls this to create a new tool.
    HARD RULE: Only writes inside TOOLS_DIR. Rejects path traversal.
    """
    # Sanitize filename
    filename = os.path.basename(filename)
    if not filename.endswith(".py"):
        filename += ".py"

    target = os.path.realpath(os.path.join(TOOLS_DIR, filename))
    allowed = os.path.realpath(TOOLS_DIR)

    if not target.startswith(allowed):
        return f"BLOCKED: Cannot write outside /tools"

    with open(target, "w") as f:
        f.write(code)

    # Immediately load it
    success = load_tool_module(target)
    if success:
        return f"Tool '{filename}' created and loaded successfully."
    else:
        return f"Tool '{filename}' written but failed to load — check code."

# ── Watchdog handler ───────────────────────────────────────────────────────────
class ToolChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            logger.info(f"[watchdog] Change detected: {event.src_path}")
            load_tool_module(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            logger.info(f"[watchdog] New file: {event.src_path}")
            load_tool_module(event.src_path)

def start_watcher():
    observer = Observer()
    observer.schedule(ToolChangeHandler(), TOOLS_DIR, recursive=False)
    observer.start()
    logger.info("[watchdog] Watching /tools for changes...")
    return observer
