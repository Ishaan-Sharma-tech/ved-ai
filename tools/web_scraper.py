import httpx
from bs4 import BeautifulSoup
import re
import logging
from core.corporate.utils import _resilient_chat

logger = logging.getLogger("aether.web_scraper")

TOOL_NAME = "web_scraper"
TOOL_DESCRIPTION = "Scrape a website URL to extract details. Set query parameter to extract specific intel."

async def run(**kwargs) -> str:
    """Scrape a URL and optionally extract text using LLM."""
    url = kwargs.get("url") or kwargs.get("link") or kwargs.get("endpoint") or ""
    query = kwargs.get("query") or kwargs.get("search") or kwargs.get("prompt") or ""
    
    if not url: return "URL is required for web scraper."
    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Kill all script and style elements safely
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            script.extract()
            
        text = soup.get_text()
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit text to roughly 6k tokens (~25k chars) to easily fit into Llama's context
        text = text[:25000]

        if not query:
            return f"Scraped Data from {url} (Truncated):\n{text[:2000]}"
            
        messages = [
            {"role": "system", "content": f"You are a highly capable data extraction bot. Extract EXACTLY what the user wants from the raw scraped webpage text below. Be direct, concise, and heavily structured. Do not use conversational filler.\n\nRaw Text:\n{text}"},
            {"role": "user", "content": query}
        ]
        
        logger.info(f"Web scraper extracting: '{query}' from {url}")
        
        # Using general (8b) because it is faster and easily understands extraction schemas
        result = await _resilient_chat(messages, "llama-3.1-8b-instant", role="worker")
        return result
        
    except httpx.HTTPError as e:
        return f"Network error scraping {url}: {e}"
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        return f"Failed to scrape {url}: {e}"
