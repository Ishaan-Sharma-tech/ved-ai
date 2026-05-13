"""
Screen reader — takes a screenshot and uses Gemini vision to describe screen content.

NOTE: In voice mode with LiveKit, Gemini already has real-time screen access via 
      the video_sampler/screen share. This tool is a FALLBACK for:
      1. Chat mode (no LiveKit room)
      2. Explicit "verify what happened" calls from the LLM
"""

import asyncio
import logging
import base64
import io
from datetime import datetime
from core.config import get_workspace

TOOL_NAME = "screen_reader"
TOOL_DESCRIPTION = "See and describe what's currently on screen — ask questions about screen content"

logger = logging.getLogger("aether.tools.screen_reader")


async def _analyze_with_gemini(prompt: str, image_base64: str) -> str:
    """Send image to Gemini vision API directly (no OpenRouter dependency)."""
    import httpx
    from core.config import get_api_key

    key = get_api_key("gemini")
    if not key:
        raise ValueError("No Gemini API key configured")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}}
            ]
        }],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def run(**kwargs) -> str:
    """
    Take a screenshot and analyze it with Gemini vision.
    Args:
        query: what to look for or ask about the screen
    """
    query = kwargs.get("query") or kwargs.get("question") or kwargs.get("prompt") or "What is on the screen right now?"
    try:
        from PIL import ImageGrab

        sd = get_workspace() / "screenshots"
        sd.mkdir(parents=True, exist_ok=True)

        # Take screenshot
        img = await asyncio.to_thread(ImageGrab.grab)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = sd / f"screen_{timestamp}.jpg"

        def _compress_and_save(image, path):
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            max_width = 1280
            if image.width > max_width:
                ratio = max_width / float(image.width)
                new_height = int((float(image.height) * float(ratio)))
                image = image.resize((max_width, new_height))
            image.save(path, format="JPEG", quality=65)

        # Compress heavily down to ~150KB to eliminate upload network bottleneck
        await asyncio.to_thread(_compress_and_save, img, str(save_path))

        # Read as base64
        img_bytes = save_path.read_bytes()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        logger.info(f"Compressed screenshot: {save_path.name} ({len(img_bytes)//1024} KB), analyzing...")

        # Analyze with Gemini Vision API directly (not OpenRouter)
        result = await _analyze_with_gemini(prompt=query, image_base64=img_b64)

        return f"Screen analysis:\n{result}\n\n(Screenshot saved: {save_path.name})"

    except ImportError:
        return "Screenshot requires Pillow. Run: pip install Pillow"
    except Exception as e:
        logger.error(f"Screen reader error: {e}")
        return f"Screen read failed: {e}"
