"""
Image Generator tool — free image generation via pollinations.ai
"""

import httpx
import os
import urllib.parse
import uuid
import logging
from core.config import get_workspace

logger = logging.getLogger("aether.tools.image_generator")

TOOL_NAME = "image_generator"
TOOL_DESCRIPTION = "Generate an image unconditionally from a text prompt using Pollinations AI."

async def run(**kwargs) -> str:
    prompt = kwargs.get("prompt") or kwargs.get("query") or kwargs.get("text") or ""
    try:
        seed = int(kwargs.get("seed")) if kwargs.get("seed") is not None else None
    except (ValueError, TypeError):
        seed = None
    filename = kwargs.get("filename") or kwargs.get("file") or kwargs.get("name") or None
    
    if not prompt: return "Prompt is required."
    ws = get_workspace()
        
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true"
    if seed is not None:
        url += f"&seed={seed}"
        
    if not filename:
        filename = f"gen_img_{uuid.uuid4().hex[:8]}.jpg"
    elif not filename.endswith(".jpg"):
        filename += ".jpg"
        
    filepath = ws / filename
    
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            
            with open(filepath, "wb") as f:
                f.write(resp.content)
                
        return f"Image successfully generated and saved to {filepath}"
    except Exception as e:
        logger.error(f"Image gen failed: {e}")
        return f"Failed to generate image: {e}"
