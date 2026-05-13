import os
import json
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.paid_router")

# Lazy-init HTTP client (module-level clients can break if event loop changes)
_shared_http_client: httpx.AsyncClient | None = None

def _get_http_client() -> httpx.AsyncClient:
    global _shared_http_client
    if _shared_http_client is None or _shared_http_client.is_closed:
        _shared_http_client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
        )
    return _shared_http_client

async def chat(messages: list, task_type: str = "general", stream: bool = True):
    """
    Paid Router: Uses OpenAI or Claude based on available keys.
    """
    from core.config import get_api_key
    
    # Try OpenAI first, then Claude
    openai_key = os.environ.get("OPENAI_API_KEY")
    claude_key = os.environ.get("CLAUDE_API_KEY")
    
    if openai_key:
        return await _chat_openai(messages, openai_key, stream, task_type)
    elif claude_key:
        return await _chat_claude(messages, claude_key, stream, task_type)
    else:
        # Fallback to Free Tier (Groq) if Paid requested but no keys
        logger.warning("Paid Tier requested but no OpenAI/Claude keys found. Falling back to Groq.")
        from core.groq_router import chat as groq_chat
        return await groq_chat(messages, task_type, stream)

async def _chat_openai(messages, key, stream, task_type):
    model = "gpt-4o-mini" # User can upgrade to gpt-4o
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": 0.7
    }
    
    if not stream:
        resp = await _get_http_client().post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"], model, task_type

    async def _gen():
        async with _get_http_client().stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    raw = line[6:].strip()
                    if raw == "[DONE]": break
                    try:
                        data = json.loads(raw)
                        chunk = data["choices"][0]["delta"].get("content", "")
                        if chunk: yield chunk
                    except: pass
                    
    return _gen(), model, task_type

async def _chat_claude(messages, key, stream, task_type):
    """Claude API support — falls back to Groq if not yet implemented."""
    logger.warning("Claude direct integration pending. Falling back to Groq.")
    from core.groq_router import chat as groq_chat
    return await groq_chat(messages, task_type, stream)
