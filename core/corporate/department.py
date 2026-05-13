import json
import logging
import uuid
import asyncio
from typing import List

from core.corporate.utils import _resilient_chat
from core.corporate.blackboard import GlobalBlackboard
from core.memory import save_turn
from tool_runtime.loader import load_manifest, TOOL_REGISTRY
from core.tool_schemas import load_schemas

logger = logging.getLogger("aether.corporate.department")

from core.corporate.tool_utils import _safe_run_tool, _is_destructive, PENDING_AUTH

class DepartmentHead:
    def __init__(self, name: str, description: str, tools: List[str]):
        self.name = name
        self.description = description
        self.tools = tools
        self.model = "llama-3.3-70b-versatile" # Worker model for high capability tasks

    async def run(self, task: str, blackboard: GlobalBlackboard, session_id: str, _push=None) -> str:
        """
        Executes the assigned task using internal Worker <-> QA loops.
        Maximum 3 iterations allowed.
        """
        if _push:
            await _push(f"🏢 **{self.name}** received task. Initiating internal workflow...")
            
        manifest = load_manifest()
        schemas = load_schemas()
        
        my_tools = {k: v for k, v in manifest.items() if k in self.tools}
        tool_lines = []
        for name, info in my_tools.items():
            desc = info.get("description", "")
            schema = schemas.get(name, {})
            req = schema.get("required", [])
            valid_acts = schema.get("valid_actions", [])
            rules = []
            if req: rules.append(f"Requires: {req}")
            if valid_acts: rules.append(f"Actions: {valid_acts}")
            schema_str = f" ({', '.join(rules)})" if rules else ""
            tool_lines.append(f"- {name}: {desc}{schema_str}")
        tool_info = "\n".join(tool_lines)

        base_prompt = f"""You are the {self.name}. {self.description}
Goal: "{task}"

Available tools:
{tool_info}

Determine the tool calls needed to accomplish this goal. You can execute multiple tools in sequence if needed.
Return ONLY a raw JSON array of objects, with no markdown formatting.
[{{ "tool": "tool_name", "args": {{"arg1": "value"}}, "reason": "why" }}]
If no tools are needed to satisfy this, return an empty array [].
"""

        max_loops = 3
        current_state = ""
        final_summary = ""
        
        for iteration in range(max_loops):
            if _push:
                await _push(f"⚙️ {self.name} is working... (Iteration {iteration+1}/{max_loops})")
                
            prompt = base_prompt
            if current_state:
                prompt += f"\n\nPrevious actions and results:\n{current_state}\nBased on these results, do you need to call more tools to fix issues or complete the task? If the task is fully complete and verified, output an empty array []."
                
            messages = [{"role": "system", "content": prompt}]
            response_text = await _resilient_chat(messages, self.model, role="worker", json_format=False)
            
            # Silent logging
            await save_turn(session_id, "assistant", f"[{self.name} Loop {iteration+1}] Plan: {response_text[:200]}...", "swarm_internal")
            
            try:
                start = response_text.find("[")
                end = response_text.rfind("]")
                if start != -1 and end != -1:
                    plan = json.loads(response_text[start:end+1])
                else:
                    plan = []
            except Exception:
                plan = []

            if not plan:
                if iteration == 0:
                    final_summary = "No tools required to complete the task."
                else:
                    final_summary = "Task completed successfully after internal iterations."
                break # Task is complete

            results = []
            for step in plan:
                tool = step.get("tool")
                args = step.get("args", {})
                if tool in self.tools:
                    if _is_destructive(tool, args):
                        # Security Guardrail - pause on destructive actions
                        auth_id = str(uuid.uuid4())
                        PENDING_AUTH[session_id] = {
                            "auth_id": auth_id, "tool": tool, "args": args
                        }
                        if _push:
                            await _push(f"⚠️ **Security Guardrail (from {self.name})** — Approval needed for `{tool}`.")
                        # wait up to 300 seconds
                        for _ in range(300):
                            await asyncio.sleep(1)
                            if session_id not in PENDING_AUTH:
                                break
                        if session_id in PENDING_AUTH:
                            del PENDING_AUTH[session_id]
                            results.append(f"[{tool} failed]: Authorization timed out.")
                            continue

                    try:
                        res = await _safe_run_tool(tool, args)
                        res_str = str(res)
                        results.append(f"Output of {tool}:\n{res_str[:1500]}")
                        # Silent logging
                        await save_turn(session_id, "tool", f"[{tool}] result: {res_str[:200]}...", "swarm_internal")
                    except Exception as e:
                        results.append(f"[{tool} failed]: {e}")
                        await save_turn(session_id, "tool", f"[{tool}] failed: {e}", "swarm_internal")
                else:
                    results.append(f"[{tool} failed]: Tool not allowed for {self.name}.")
                    
            if results:
                current_state += "\n".join(results) + "\n"
        
        # Compile final summary
        summary_prompt = f"""You are the {self.name}.
Your Task: {task}

Results from your internal workflow:
{current_state}

Analyze your findings and provide a final, verified summary for the Global Blackboard. 
Be concise, focus on data, and avoid pleasantries. If the task failed after maximum attempts, explain why it failed."""
        
        final_summary = await _resilient_chat([{"role": "user", "content": summary_prompt}], self.model, role="worker")
        
        # Write to blackboard
        blackboard.write(self.name, final_summary)
        
        if _push:
            await _push(f"✅ **{self.name}** posted findings to the Blackboard.")
            
        return final_summary
