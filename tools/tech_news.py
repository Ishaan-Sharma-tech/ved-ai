# TOOL_NAME = "tech_news"
# TOOL_DESCRIPTION = "Fetch top 5 trending stories from HackerNews API"

TOOL_NAME = "tech_news"
TOOL_DESCRIPTION = "Fetch top 5 trending stories from HackerNews API and return title and URL as a clean, readable list"

import logging
import json
import aiohttp

logger = logging.getLogger("aether.tech_news")

async def run(**kwargs):
    try:
        top_stories_count = int(kwargs.get("top_stories_count", 5))
    except ValueError:
        logger.error("Invalid input: top_stories_count must be an integer.")
        return "Invalid input: top_stories_count must be an integer."

    if top_stories_count < 1:
        logger.error("Invalid input: top_stories_count must be a positive integer.")
        return "Invalid input: top_stories_count must be a positive integer."

    async with aiohttp.ClientSession() as session:
        async with session.get("https://hacker-news.firebaseio.com/v0/topstories.json") as resp:
            if resp.status == 200:
                top_stories_ids = await resp.json()
                top_stories_ids = top_stories_ids[:top_stories_count]

                results = []
                for story_id in top_stories_ids:
                    async with session.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json") as resp:
                        if resp.status == 200:
                            story_data = await resp.json()
                            results.append({"title": story_data.get("title"), "url": story_data.get("url")})

                return json.dumps(results, indent=4)

            else:
                logger.error(f"Failed to retrieve top stories: {resp.status}")
                return f"Failed to retrieve top stories: {resp.status}"

# TOOL NAME
# TOOL DESCRIPTION

# TOOL CODE