import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.gemini_router")

def classify_task(message: str) -> str:
    """Simple keyword classifier — returns task type."""
    msg = message.lower()
    coding_kw = ["code", "tool", "script", "function", "bug", "error", "python", "write a", "create a tool", "build"]
    research_kw = ["research", "explain", "summarize", "write about", "essay", "article", "what is", "how does", "search"]
    for kw in coding_kw:
        if kw in msg:
            return "coding"
    for kw in research_kw:
        if kw in msg:
            return "research"
    return "general"

def _format_messages(messages: list) -> dict:
    contents = []
    system_instruction = None
    
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "system":
            system_instruction = {"parts": [{"text": content}]}
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})
            
    payload = {"contents": contents}
    if system_instruction:
        payload["systemInstruction"] = system_instruction
        
    return payload

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

async def chat(messages: list, task_type: str = None, stream: bool = True):
    """
    Send messages to Gemini models with round-robin key rotation.
    Returns an async generator of text chunks if stream=True.
    """
    if task_type is None:
        task_type = classify_task(messages[-1]["content"] if messages else "")

    payload = _format_messages(messages)
    payload["generationConfig"] = {
        "temperature": 0.7,
        "maxOutputTokens": 2048,
    }

    async def _stream_generator():
        from core.config import get_api_key
        
        # We try up to 3 keys if one fails
        for attempt in range(1, 4):
            try:
                key = get_api_key("gemini")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?key={key}&alt=sse"
                
                async with _get_http_client().stream("POST", url, json=payload) as response:
                    if response.status_code == 429:
                        logger.warning(f"Gemini Key {attempt} hit rate limit (429). Retrying...")
                        continue
                    
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            try:
                                data = json.loads(raw)
                                text = data["candidates"][0]["content"]["parts"][0]["text"]
                                yield text
                            except Exception:
                                pass
                return  # Success, exit generator
            except httpx.HTTPError as e:
                logger.warning(f"Gemini attempt {attempt} network error: {e}")
                if attempt < 3: continue
                yield f"\n[Network Error: {e}]"
                return
            except Exception as e:
                logger.error(f"Gemini attempt {attempt} system error: {e}")
                if attempt < 3: continue
                yield f"\n[System Error: {e}]"
                return
                
        yield "Arre yaar, saari Gemini keys fail ho rahi hain. Ek baar settings check karo."

    if stream:
        return _stream_generator(), "gemini-2.0-flash", task_type
    
    # Fallback to non-streaming if specifically requested
    from core.config import get_api_key
    key = get_api_key("gemini")
    sync_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    resp = await _get_http_client().post(sync_url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"], "gemini-2.0-flash", task_type
