import json
import os
import logging
from pathlib import Path

logger = logging.getLogger("aether.schemas")

# Use project-relative path
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMAS_FILE = PROJECT_ROOT / "tools" / "schemas.json"

def load_schemas() -> dict:
    """Loads tool schemas from the JSON file."""
    if not SCHEMAS_FILE.exists():
        logger.warning(f"Schema file not found at {SCHEMAS_FILE}")
        return {}
    try:
        with open(SCHEMAS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load schemas: {e}")
        return {}

def save_schema(tool_name: str, schema: dict):
    """Adds or updates a schema for a specific tool."""
    schemas = load_schemas()
    schemas[tool_name] = schema
    try:
        with open(SCHEMAS_FILE, "w") as f:
            json.dump(schemas, f, indent=2)
        logger.info(f"Schema for '{tool_name}' saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save schema for {tool_name}: {e}")

def validate_and_fix(tool_name: str, args: dict) -> dict:
    """
    Validate and auto-fix classifier output args against tool schema.
    Returns corrected args dict.
    """
    schemas = load_schemas()
    schema = schemas.get(tool_name)
    if not schema:
        return args

    fixed = dict(args)

    # Fix action aliases
    if "action" in fixed and "action_aliases" in schema:
        action = str(fixed["action"]).lower().strip()
        if action not in schema.get("valid_actions", []):
            alias = schema["action_aliases"].get(action)
            if alias:
                fixed["action"] = alias

    # Fix invalid arg names (e.g. screen_reader gets 'text' instead of 'query')
    if "invalid_args" in schema:
        for bad_arg in schema["invalid_args"]:
            if bad_arg in fixed:
                fixed["query"] = fixed.pop(bad_arg)

    # Apply defaults for missing optional args
    if "defaults" in schema:
        for key, val in schema["defaults"].items():
            if key not in fixed:
                fixed[key] = val

    return fixed

