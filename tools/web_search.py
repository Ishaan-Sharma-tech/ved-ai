import os
import logging
from tavily import AsyncTavilyClient
from dotenv import load_dotenv

load_dotenv()

TOOL_NAME = "web_search"
TOOL_DESCRIPTION = "Search the web for real-time information, news, facts, prices, scores, anything current"

logger = logging.getLogger("aether.tools.web_search")

_client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def _clean_snippet(content: str, max_chars: int = 150) -> str:
    """Take first complete sentence up to max_chars."""
    content = content.replace("\n", " ").strip()
    sentences = content.split(". ")
    result = ""
    for s in sentences:
        if len(result) + len(s) > max_chars:
            break
        result += s + ". "
    return result.strip() or content[:max_chars] + "..."


def _format_for_text(query: str, results: list, answer: str) -> str:
    """Clean, concise format for text mode."""
    lines = []

    if answer:
        # Trim answer to 2 sentences max
        sentences = answer.replace("\n", " ").split(". ")
        short_answer = ". ".join(sentences[:2]).strip()
        if not short_answer.endswith("."):
            short_answer += "."
        lines.append(f"**{short_answer}**\n")

    lines.append(f"Sources:\n")
    for i, r in enumerate(results[:3], 1):  # max 3 sources
        title = r.get("title", "")[:60]
        url = r.get("url", "")
        snippet = _clean_snippet(r.get("content", ""), 120)
        lines.append(f"{i}. **{title}**")
        lines.append(f"   {url}")
        if snippet:
            lines.append(f"   {snippet}\n")

    return "\n".join(lines)


def _format_for_voice(answer: str, results: list) -> str:
    """2 sentences max for voice."""
    if answer:
        sentences = answer.replace("\n", " ").split(". ")
        voice = ". ".join(sentences[:2]).strip()
        return voice if voice.endswith(".") else voice + "."
    if results:
        return _clean_snippet(results[0].get("content", ""), 200)
    return "I couldn't find anything relevant."


async def run(**kwargs) -> str:
    query = kwargs.get("query") or kwargs.get("search") or kwargs.get("prompt") or ""
    mode = kwargs.get("mode", "text")
    try:
        max_results = int(kwargs.get("max_results", 3))
    except (ValueError, TypeError):
        max_results = 3
        
    if not query:
        return "Please provide a search query."

    # Absorb extra kwargs into query if they weren't quoted properly
    extra_keys = set(kwargs.keys()) - {"query", "search", "prompt", "mode", "max_results"}
    extra = " ".join(str(kwargs[k]) for k in extra_keys if kwargs[k])
    
    if extra:
        query = f"{query} {extra}".strip()

    logger.info(f"Searching: '{query}' (mode={mode})")

    try:
        response = await _client.search(
            query=query,
            max_results=int(max_results),
            search_depth="advanced",
            include_answer=True,
        )

        results = response.get("results", [])
        answer = response.get("answer", "")

        if not results and not answer:
            return f"No results found for: {query}"

        if mode == "voice":
            return _format_for_voice(answer, results)
        else:
            return _format_for_text(query, results, answer)

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Search failed: {e}"
