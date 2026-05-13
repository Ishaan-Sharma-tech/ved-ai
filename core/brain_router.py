"""
Brain Router — Legacy bridge for the new Corporate Swarm engine.
Ensures existing tools and modules still function without 'groq_router'.
"""
from core.corporate.utils import _resilient_chat

async def chat(messages: list, task_type: str = "general", stream: bool = False):
    """Bridge for legacy code to use the new Corporate Resilient Chat."""
    # Note: Worker logic is now non-streaming.
    response = await _resilient_chat(messages, model="llama-3.1-8b-instant", role="freelance")
    return response, "llama-3.1-8b-instant", "chat"

def classify_task(message: str) -> str:
    """Legacy bridge for task type detection."""
    return "general"
