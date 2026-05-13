TOOL_NAME = "youtube_audio_downloader"
TOOL_DESCRIPTION = "Download YouTube audio as MP3 using yt-dlp"

import logging
import asyncio
from typing import Optional

logger = logging.getLogger("aether.youtube_audio_downloader")

async def run(**kwargs):
    """
    Download YouTube audio as MP3 using yt-dlp.
    
    Args:
    url (str): YouTube video URL.
    output (str, optional): Output file path. Defaults to "output.mp3".
    quality (str, optional): Video quality. Defaults to "bestaudio".
    format (str, optional): Output format. Defaults to "mp3".
    """

    url: Optional[str] = kwargs.get('url')
    output: Optional[str] = kwargs.get('output')
    quality: Optional[str] = kwargs.get('quality')
    format: Optional[str] = kwargs.get('format')

    if not url:
        logger.error("URL is required.")
        return "URL is required."

    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed. Please install it using `pip install yt-dlp`.")
        return "yt-dlp is not installed. Please install it using `pip install yt-dlp`."

    # Replace 'YOUR_API_KEY_HERE' with your actual API key
    api_key = 'YOUR_API_KEY_HERE'

    ydl_opts = {
        'format': format or 'best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output or 'output.mp3',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            ydl.download([url])
    except Exception as e:
        logger.error(f"Failed to download audio: {e}")
        return f"Failed to download audio: {e}"

    return "Audio downloaded successfully."