"""
Corporate Swarm Orchestrator
Spawns specialized hierarchical departments to concurrently solve a goal.
"""
import asyncio
import time
import logging

from core.corporate.blackboard import GlobalBlackboard
from core.corporate.ceo import CorporateCEO, engineering_dept, research_dept, admin_dept, data_dept, ops_dept
from core.memory import save_turn

logger = logging.getLogger("aether.swarm")

_active_swarms: dict = {}
_push_fns: dict = {}

def set_swarm_push_fn(fn, session_id: str = "global"):
    """Register the push callback for specific swarm updates."""
    if fn:
        _push_fns[session_id] = fn
    elif session_id in _push_fns:
        del _push_fns[session_id]

def get_active_swarms() -> dict:
    return _active_swarms.copy()

def cancel_swarm(swarm_id: str) -> str:
    if swarm_id in _active_swarms:
        _active_swarms[swarm_id]["status"] = "cancelled"
        return f"✋ Swarm `{swarm_id}` cancelled."
    return f"No active swarm `{swarm_id}`."

class SwarmOrchestrator:
    async def run(self, goal: str, session_id: str, swarm_id: str):
        _active_swarms[swarm_id] = {"status": "running", "goal": goal, "created_at": time.time()}

        async def _push(msg: str):
            fn = _push_fns.get(session_id)
            if fn:
                try:
                    await fn(msg, session_id)
                except Exception:
                    pass

        blackboard = GlobalBlackboard()
        ceo = CorporateCEO()
        
        assignments = await ceo.delegate(goal, blackboard, session_id, _push)
        
        if not assignments:
            await _push("⚠️ CEO assigned no parallel tasks. The goal might be too simple or unclear.")
            _active_swarms.pop(swarm_id, None)
            return

        await _push(f"🌟 **Corporate Swarm activated:** {len(assignments)} departments assigned.")
        
        tasks_coros = []
        for idx, assign in enumerate(assignments):
            dept_name = assign.get("dept")
            task_desc = assign.get("task")
            if not dept_name or not task_desc:
                continue
            
            dept = None
            if dept_name == "Engineering":
                dept = engineering_dept
            elif dept_name == "Research":
                dept = research_dept
            elif dept_name == "Administrative":
                dept = admin_dept
            elif dept_name == "Data":
                dept = data_dept
            elif dept_name == "Operations":
                dept = ops_dept
                
            if dept:
                async def _run_dept(d=dept, t=task_desc):
                    await d.run(t, blackboard, session_id, _push)
                tasks_coros.append(_run_dept())

        if not tasks_coros:
            await _push("❌ No valid departments assigned.")
            _active_swarms.pop(swarm_id, None)
            return

        # Run departments in parallel
        await asyncio.gather(*tasks_coros)
        
        if _active_swarms.get(swarm_id, {}).get("status") == "cancelled":
            await _push("🛑 Swarm was cancelled.")
            _active_swarms.pop(swarm_id, None)
            return

        # Synthesize final response from Blackboard
        final_report = await ceo.synthesize(goal, blackboard, session_id, _push)
        
        final_msg = f"🏁 **Swarm Complete**\n\n{final_report}"
        await _push(final_msg)
        
        await save_turn(session_id, "user", f"[Corporate Task] {goal}", "swarm")
        await save_turn(session_id, "assistant", final_msg, "swarm", "swarm")

        _active_swarms[swarm_id]["status"] = "done"

        # Cleanup after 10 mins
        await asyncio.sleep(600)
        _active_swarms.pop(swarm_id, None)
