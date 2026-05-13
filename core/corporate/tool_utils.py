import logging
from core.tool_schemas import validate_and_fix
from tool_runtime.loader import TOOL_REGISTRY

logger = logging.getLogger("aether.corporate.tool_utils")

# Shared state for security authorizations
PENDING_AUTH = {}

def _is_destructive(tool_name: str, args: dict) -> bool:
    """Security check for sensitive actions."""
    action = args.get("action", "").lower()
    if tool_name == "file_manager" and action == "delete": return True
    if tool_name == "drive" and action == "delete": return True
    if tool_name == "gmail" and action == "send": return True
    if tool_name == "system_control" and action == "empty_trash": return True
    return False

async def _safe_run_tool(tool_name: str, args: dict) -> str:
    """Run a tool with full error boundary and schema validation."""
    if tool_name not in TOOL_REGISTRY:
        return f"Tool '{tool_name}' not found."
    try:
        # Validate args against schema
        safe_args = validate_and_fix(tool_name, args)
        result = await TOOL_REGISTRY[tool_name](**safe_args)
        return str(result) if result is not None else "Done."
    except Exception as e:
        logger.error(f"Tool {tool_name} error: {e}")
        return f"Tool '{tool_name}' error: {e}"
