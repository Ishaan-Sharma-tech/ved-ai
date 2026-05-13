"""
YouTube summarizer — paste URL, get summary via Gemini.
Uses youtube-transcript-api (free, no API key needed).
"""

import re
import asyncio
import logging
from core.corporate.utils import _resilient_chat

TOOL_NAME = "youtube_summarizer"
TOOL_DESCRIPTION = "Summarize any YouTube video — paste the URL and get key points"

logger = logging.getLogger("aether.tools.youtube")


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def run(**kwargs) -> str:
    """
    Summarize a YouTube video.
    Args:
        url: YouTube video URL
        query: optional specific question about the video
    """
    url = kwargs.get("url") or kwargs.get("link") or kwargs.get("endpoint") or ""
    query = kwargs.get("query") or kwargs.get("search") or kwargs.get("prompt") or ""
    if not url:
        return "YouTube URL bata yaar."

    video_id = _extract_video_id(url)
    if not video_id:
        return f"Valid YouTube URL nahi lagta: {url}"

    logger.info(f"Summarizing YouTube: {video_id}")

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = await asyncio.to_thread(
            YouTubeTranscriptApi.get_transcript, video_id, languages=["en", "hi", "en-IN"]
        )
        # Combine transcript
        full_text = " ".join(t["text"] for t in transcript_list)
        # Truncate to 6000 chars for Gemini
        if len(full_text) > 6000:
            full_text = full_text[:6000] + "... [truncated]"

        prompt = query if query else "Summarize this video in 5-7 key points. Be concise and clear."
        messages = [
            {"role": "system", "content": "You are Ved, a smart assistant. Summarize the YouTube video transcript below concisely and clearly."},
            {"role": "user", "content": f"{prompt}\n\nTranscript:\n{full_text}"}
        ]
        summary = await _resilient_chat(messages, "llama-3.1-8b-instant", role="worker")
        return f"YouTube Summary (ID: {video_id}):\n\n{summary}"

    except ImportError:
        return "youtube-transcript-api install kar: pip install youtube-transcript-api"
    except Exception as e:
        if "TranscriptsDisabled" in str(e):
            return "Is video mein transcript/captions disabled hain yaar."
        if "NoTranscriptFound" in str(e):
            return "English ya Hindi transcript nahi mili is video mein."
        return f"Summary nahi bana: {e}"
