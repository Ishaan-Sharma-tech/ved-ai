import os
import logging
import json
from pathlib import Path
from tool_runtime.loader import write_tool, TOOL_REGISTRY, TOOLS_DIR
from core.tool_schemas import save_schema, load_schemas

logger = logging.getLogger("aether.meta_developer")

TOOL_NAME = "meta_developer"
TOOL_DESCRIPTION = "Advanced tool for Aether to evolve its own capabilities. Can list, read, create, or delete other tools. Allows for zero-downtime evolution."

async def run(**kwargs):
    """
    Manages Aether's tool library.
    """
    action = kwargs.get("action", "list").lower().strip()
    
    # LLM resilience: check for common hallucinated arg names
    name = kwargs.get("name") or kwargs.get("tool_name") or ""
    code = kwargs.get("code") or kwargs.get("tool_code") or kwargs.get("source_code") or ""
    schema = kwargs.get("schema") or kwargs.get("tool_schema") or None
    

    if action == "list":
        schemas = load_schemas()
        summary = []
        for t_name, t_func in TOOL_REGISTRY.items():
            t_schema = schemas.get(t_name, {})
            summary.append(f"• **{t_name}**: {t_schema.get('description', 'No description')}")
        return "Loaded Tools:\n" + "\n".join(summary)

    if action == "read":
        if not name: return "Error: 'name' is required for 'read' action."
        tool_path = os.path.join(TOOLS_DIR, f"{name}.py")
        if not os.path.exists(tool_path):
            return f"Error: Tool '{name}' not found at {tool_path}"
        try:
            with open(tool_path, "r", encoding="utf-8") as f:
                return f"Source code for '{name}':\n\n```python\n{f.read()}\n```"
        except Exception as e:
            return f"Error reading tool '{name}': {e}"

    if action == "create":
        prompt = kwargs.get("prompt") or kwargs.get("query") or kwargs.get("description") or ""
        
        if not code and not prompt:
            return "Error: 'code' or 'prompt' is required to create a tool."
            
        if not name:
            import re
            name = re.sub(r'[^a-z0-9_]', '', prompt.lower().replace(' ', '_'))[:20]
            if not name:
                name = "auto_generated_tool"
            
        if not code and prompt:
            from core.corporate.utils import _resilient_chat
            from core.corporate.vault import GROQ_VAULT
            
            sys_msg = """You are Aether's internal core developer agent. Write fully functional, robust Python tools.
RULES:
1. You MUST define `TOOL_NAME` and `TOOL_DESCRIPTION` as string variables at the module level.
2. You MUST define an asynchronous run function: `async def run(**kwargs):`. It must return a string.
3. Use `import logging` and `logger = logging.getLogger("aether.your_tool_name")`.
4. Extract args safely from `kwargs`. Wrap numeric conversions in try/except.
5. Output MUST contain exactly two blocks:
   - A markdown Python code block ```python ... ``` containing the ACTUAL tool code.
   - A markdown JSON code block ```json ... ``` with the OpenAPI-style JSON schema for the parameters.
6. Return NO OTHER TEXT."""
            
            logger.info(f"[meta_developer] Autonomously generating tool '{name}'...")
            messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": f"Tool name: {name}\nGoal: {prompt}"}]
            
            try:
                response = await _resilient_chat(messages, "llama-3.3-70b-versatile", role="worker")
                import re
                code_match = re.search(r"```python\n(.*?)\n```", response, re.DOTALL | re.IGNORECASE)
                if not code_match:
                    code_match = re.search(r"```python(.*?)```", response, re.DOTALL | re.IGNORECASE)
                json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL | re.IGNORECASE)
                if not json_match:
                    json_match = re.search(r"```json(.*?)```", response, re.DOTALL | re.IGNORECASE)
                
                if code_match:
                    code = code_match.group(1).strip()
                else:
                    return f"FAILED: LLM did not return Python code. Raw output:\n{response}"
                    
                if json_match:
                    try:
                        schema = json.loads(json_match.group(1).strip())
                    except Exception:
                        pass
            except Exception as e:
                return f"FAILED: LLM tool generation error: {e}"
        
        # 0. Syntax check
        import ast
        try:
            ast.parse(code)
        except SyntaxError as e:
            return f"FAILED: Code has syntax errors. {e.msg} at line {e.lineno}. Please fix the code and try again."
        except Exception as e:
            return f"FAILED: Preliminary code check failed: {e}"

        # 1. Write the Python file
        # write_tool in loader.py handles sanitization and loading
        result = write_tool(name, code)
        
        # 2. Save the schema if provided
        if schema:
            save_schema(name, schema)
            result += f" Schema for '{name}' registered successfully."
        else:
            # Create a basic default schema if none provided
            save_schema(name, {"required": [], "description": "Auto-generated tool."})
            result += f" Warning: No schema provided. Registered basic default schema for '{name}'."
            
        return result

    if action == "delete":
        if not name: return "Error: 'name' is required for 'delete' action."
        if name == "meta_developer": return "Error: Cannot delete the meta_developer tool. This would break the evolution loop."
        
        tool_path = os.path.join(TOOLS_DIR, f"{name}.py")
        deleted_files = False
        if os.path.exists(tool_path):
            os.remove(tool_path)
            deleted_files = True
            
        # Remove from schema JSON
        schemas = load_schemas()
        if name in schemas:
            del schemas[name]
            # Manual save since we don't have a delete_schema helper yet
            SCHEMAS_PATH = Path(TOOLS_DIR) / "schemas.json"
            with open(SCHEMAS_PATH, "w") as f:
                json.dump(schemas, f, indent=2)
            deleted_files = True
            
        if deleted_files:
            # Remove from registry
            if name in TOOL_REGISTRY:
                del TOOL_REGISTRY[name]
            return f"Tool '{name}' has been deleted and unregistered."
        else:
            return f"Tool '{name}' not found."

    return f"Unknown action: {action}. Valid actions: list, read, create, delete."
