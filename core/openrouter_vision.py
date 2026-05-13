import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.vision")

from core.config import get_api_key

async def _call_vision_engine(messages: list) -> str:
    mode = os.environ.get("TIER_MODE", "free").lower()
    
    if mode == "paid":
        # Use Paid Gemini for Vision
        key = get_api_key("gemini")
        # Reuse gemini_router logic but for non-stream content
        from core.gemini_router import chat as gemini_chat
        resp, model, task = await gemini_chat(messages, "vision", stream=False)
        return resp
    
    # Otherwise Free Tier (OpenRouter)
    last_error = None
    for _ in range(3):
        try:
            key = get_api_key("openrouter")
            payload = {
                "model": "nvidia/nemotron-nano-12b-v2-vl:free",
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.4
            }
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://127.0.0.1:8000",
                "X-Title": "Aether AI"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                if resp.status_code == 429:
                    logger.warning(f"OpenRouter key rate limited, trying next")
                    last_error = "Rate limit (429)"
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = str(e)
            logger.warning(f"OpenRouter vision failed: {e}")
            continue
            
    return f"Vision analysis failed: {last_error}"

async def analyze_image(prompt: str, image_base64: str, mime_type: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}
                }
            ]
        }
    ]
    return await _call_vision_engine(messages)

async def analyze_document(prompt: str, text_content: str) -> str:
    full_prompt = f"{prompt}\n\nDocument content:\n{text_content[:8000]}"
    messages = [{"role": "user", "content": full_prompt}]
    return await _call_vision_engine(messages)
