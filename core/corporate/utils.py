import asyncio
import logging
from groq import AsyncGroq
from core.corporate.vault import GROQ_VAULT

logger = logging.getLogger("aether.corporate.utils")

async def _resilient_chat(messages: list, model: str, role: str = "worker", json_format: bool = False) -> str:
    """Auto-recovery loop for Groq 429 rate limits."""
    max_retries = 3
    
    for attempt in range(max_retries):
        if role == "classifier":
            api_key = GROQ_VAULT.get_universal_key()
        elif role in ["ceo", "freelance"]:
            api_key = GROQ_VAULT.get_executive_key(role)
        else:
            api_key = GROQ_VAULT.get_worker_key()
            
        if not api_key:
            return "Error: No API key available for role: " + role
            
        try:
            client = AsyncGroq(api_key=api_key, timeout=20.0)
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
            }
            if json_format:
                kwargs["response_format"] = {"type": "json_object"}
                
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate limit" in err_str.lower():
                logger.warning(f"[429 Rate Limit] Retrying with new key (Attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(1) # Small backoff before rotating key
                continue
            else:
                logger.error(f"Agent chat failed: {e}")
                return f"Error: {e}"
                
    return "Error: Maximum retries reached due to API rate limits."
