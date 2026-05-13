import logging
from core.corporate.utils import _resilient_chat
from core.memory import save_turn

logger = logging.getLogger("aether.corporate.freelance")

class FreelanceAgent:
    """
    Fast-Track Agent for simple tasks and general chat.
    Bypasses the corporate swarm entirely for instant responses.
    Uses Key 2 (Freelance Key) to avoid blocking workers.
    """
    def __init__(self):
        self.model = "llama-3.1-8b-instant"

    async def run_fast_task(self, task: str, session_id: str, messages: list = None) -> str:
        """
        messages: Should be pre-built by the orchestrator containing system prompt + recent history.
        """
        logger.info(f"Freelance Agent handling task: {task[:50]}")
        
        if not messages:
            messages = [
                {"role": "system", "content": "You are Aether, a helpful, fast AI assistant. Be direct and concise."},
                {"role": "user", "content": task}
            ]
            
        response = await _resilient_chat(messages, model=self.model, role="freelance")
        
        # Note: We save the turn here for consistency
        await save_turn(session_id, "user", task, "fast_track")
        await save_turn(session_id, "assistant", response, "fast_track", self.model)
        
        return response
