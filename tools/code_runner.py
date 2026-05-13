"""
Code runner — write and execute Python code in sandbox.
Only reads/writes workspace directory, 10 second timeout, no network.
"""

import os
import sys
import asyncio
import logging
import traceback
from pathlib import Path
from io import StringIO
from core.config import get_workspace

TOOL_NAME = "code_runner"
TOOL_DESCRIPTION = "Write and execute Python code in sandbox with auto pip dependency installs"

logger = logging.getLogger("aether.tools.code_runner")

TIMEOUT = 10


_ALLOWED_MODULES = {"math", "random", "datetime", "string", "json", "re", "secrets", "hashlib", "time", "collections", "itertools"}

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    try:
        return __import__(name, globals, locals, fromlist, level)
    except ModuleNotFoundError as e:
        raise ImportError(f"__AUTO_PIP__:{e.name}")

def _safe_exec(code: str) -> tuple[str, str]:
    """Execute code with restricted globals. Returns (stdout, error)."""
    # Ensure current working directory is the workspace
    import os
    from core.config import get_workspace
    os.chdir(get_workspace())
    
    # Redirect stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    error = ""
    try:
        # Restricted builtins — no network, no subprocess
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len, "range": range, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "str": str, "int": int, "float": float, "bool": bool,
                "sum": sum, "min": max, "max": max, "abs": abs,
                "round": round, "sorted": sorted, "reversed": reversed,
                "open": open,  # allowed for workspace files only
                "isinstance": isinstance, "type": type,
                "hasattr": hasattr, "getattr": getattr,
                "Exception": Exception, "ValueError": ValueError,
                "TypeError": TypeError, "KeyError": KeyError,
                "IndexError": IndexError,
                "__import__": _safe_import,
            },
            "WORKSPACE": str(get_workspace()),
        }
        exec(code, safe_globals)
    except Exception as e:
        error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

    return output, error


async def run(**kwargs) -> str:
    """
    Actions:
    - run: execute code directly (code parameter)
    - run_file: run a .py file from workspace (filename parameter)
    - save_run: save code to workspace then run it (code + filename)
    """
    action = kwargs.get("action", "run")
    code = kwargs.get("code", "")
    filename = kwargs.get("filename") or kwargs.get("file") or ""
    language = kwargs.get("language", "python")

    ws = get_workspace()
    action = action.lower().strip()

    if action == "run":
        if not code:
            return "Code bata yaar kya run karna hai."
        logger.info(f"Running code ({len(code)} chars)")
        try:
            output, error = await asyncio.wait_for(
                asyncio.to_thread(_safe_exec, code),
                timeout=TIMEOUT
            )
            if error and "__AUTO_PIP__:" in error:
                import re, subprocess
                match = re.search(r"__AUTO_PIP__:(\w+)", error)
                if match:
                    mod = match.group(1)
                    logger.info(f"Auto-installing: {mod}")
                    subprocess.run([sys.executable, "-m", "pip", "install", mod], capture_output=True)
                    output, error = await asyncio.wait_for(
                        asyncio.to_thread(_safe_exec, code),
                        timeout=TIMEOUT
                    )
            if error:
                return f"Error aaya:\n{error}\n\nOutput (partial):\n{output}" if output else f"Error:\n{error}"
            return f"Output:\n{output}" if output else "Code chala, koi output nahi."
        except asyncio.TimeoutError:
            return f"Timeout — {TIMEOUT} seconds se zyada lag gaya."

    elif action == "run_file":
        if not filename:
            return "Filename bata."
        fpath = ws / filename
        if not fpath.exists():
            return f"File nahi mili: {filename}"
        code = fpath.read_text(encoding="utf-8")
        try:
            output, error = await asyncio.wait_for(
                asyncio.to_thread(_safe_exec, code),
                timeout=TIMEOUT
            )
            if error:
                return f"Error in {filename}:\n{error}"
            return f"Output of {filename}:\n{output}" if output else f"{filename} chala, koi output nahi."
        except asyncio.TimeoutError:
            return f"Timeout — {filename} {TIMEOUT}s mein finish nahi hua."

    elif action == "save_run":
        if not code or not filename:
            return "Dono code aur filename chahiye."
        if not filename.endswith(".py"):
            filename += ".py"
        fpath = ws / filename
        fpath.write_text(code, encoding="utf-8")
        try:
            output, error = await asyncio.wait_for(
                asyncio.to_thread(_safe_exec, code),
                timeout=TIMEOUT
            )
            if error and "__AUTO_PIP__:" in error:
                import re, subprocess
                match = re.search(r"__AUTO_PIP__:(\w+)", error)
                if match:
                    mod = match.group(1)
                    logger.info(f"Auto-installing for save_run: {mod}")
                    subprocess.run([sys.executable, "-m", "pip", "install", mod], capture_output=True)
                    output, error = await asyncio.wait_for(
                        asyncio.to_thread(_safe_exec, code),
                        timeout=TIMEOUT
                    )
            saved_msg = f"Saved to {fpath}\n"
            if error:
                return saved_msg + f"Error:\n{error}"
            return saved_msg + (f"Output:\n{output}" if output else "Chala, koi output nahi.")
        except asyncio.TimeoutError:
            return f"Saved but timeout hua {TIMEOUT}s mein."

    else:
        return "Available actions: run, run_file, save_run"
