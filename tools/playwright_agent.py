"""
Playwright Browser Agent — Navigate JS-heavy sites, click, and interact.
"""

import os
import asyncio
import logging
from playwright.async_api import async_playwright, Error as PlaywrightError

logger = logging.getLogger("aether.tools.playwright_agent")

TOOL_NAME = "playwright_agent"
TOOL_DESCRIPTION = "Headless browser agent to interact with JS-rendered sites, click buttons, fill forms, and extract content."

# Store chromium binaries in project root to keep user's system clean
PLAYWRIGHT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".playwright_browsers")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_DIR

async def run(**kwargs) -> str:
    url = kwargs.get("url") or kwargs.get("endpoint") or kwargs.get("link") or ""
    action = kwargs.get("action", "read").lower().strip()
    css_selector = kwargs.get("css_selector") or kwargs.get("selector") or ""
    fill_text = kwargs.get("fill_text") or kwargs.get("text") or kwargs.get("value") or ""
    
    if not url: return "URL is required."
    if not url.startswith("http"):
        url = "https://" + url

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                # If chromium binaries are not installed, install them right into D: drive automatically
                logger.info(f"Chromium binary not found in {PLAYWRIGHT_DIR}. Installing via subprocess...")
                import subprocess
                subprocess.run(["playwright", "install", "chromium"], env=os.environ, check=True)
                browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            result = ""
            if action == "read":
                if css_selector:
                    locator = page.locator(css_selector)
                    await locator.first.wait_for(timeout=5000)
                    result = await locator.first.inner_text()
                else:
                    result = await page.evaluate("() => document.body.innerText")
                    result = result[:15000] # truncate
            elif action == "click":
                if not css_selector:
                    return "CSS selector required for click action."
                locator = page.locator(css_selector)
                await locator.first.click(timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=5000)
                result = f"Clicked '{css_selector}' successfully."
            elif action == "fill":
                if not css_selector or not fill_text:
                    return "CSS selector and fill_text required for fill action."
                locator = page.locator(css_selector)
                await locator.first.fill(fill_text, timeout=5000)
                result = f"Filled '{fill_text}' into '{css_selector}'."
            else:
                result = f"Unknown action: {action}"

            await browser.close()
            return f"Playwright Action ({action}) completed on {url}:\n{result}"
    except PlaywrightError as e:
        logger.error(f"Playwright error: {e}")
        return f"Browser interaction failed: {e}"
    except Exception as e:
        logger.error(f"Playwright runtime error: {e}")
        return f"Browser runtime error: {e}"
