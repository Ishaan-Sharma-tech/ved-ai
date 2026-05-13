import json
import logging
import asyncio
from core.corporate.utils import _resilient_chat
from core.corporate.blackboard import GlobalBlackboard
from core.corporate.department import DepartmentHead
from core.memory import save_turn

logger = logging.getLogger("aether.corporate.ceo")

# Predefined Departments
engineering_dept = DepartmentHead(
    name="Engineering",
    description="You write and execute code, manage files, and can build new tools.",
    tools=["code_runner", "meta_developer", "file_manager"]
)

research_dept = DepartmentHead(
    name="Research",
    description="You search the web and scrape data to gather information.",
    tools=["web_search", "web_scraper"]
)

admin_dept = DepartmentHead(
    name="Administrative",
    description="You manage emails, schedules, reminders, and personal notes.",
    tools=["gmail", "scheduler", "google_tasks", "notes"]
)

data_dept = DepartmentHead(
    name="Data",
    description="You handle cloud storage (Google Drive), large document analysis, and data extraction.",
    tools=["drive", "file_manager", "web_scraper"]
)

ops_dept = DepartmentHead(
    name="Operations",
    description="You control system settings, workspace focus modes, and hardware (volume, brightness, screenshots).",
    tools=["system_control", "workspace_manager"]
)

class CorporateCEO:
    def __init__(self):
        self.model = "qwen/qwen3-32b" # Optimized for 60 RPM high-speed delegation

    async def delegate(self, goal: str, blackboard: GlobalBlackboard, session_id: str, _push=None) -> list:
        """
        CEO decides which departments need to work on the goal.
        Returns a list of dicts: [{"dept": "Engineering", "task": "..."}]
        """
        if _push:
            await _push("🏢 **CEO** is analyzing the goal and delegating to specialized departments...")
            
        prompt = f"""You are the Corporate CEO of Aether AI Agency. Decompose the user's goal into parallel tasks.
Available Departments:
- Engineering: coding, tool creation, local file logic.
- Research: web searching, scraping.
- Administrative: Gmail, reminders, tasks, calendar/scheduler, notes.
- Data: Google Drive, file organization, large document reading.
- Operations: System volume, screenshots, workspace focus modes, PC lock.

Given Goal: "{goal}"
Assign departments that can work in PARALLEL. Only assign if strictly necessary.
Return ONLY a raw JSON array. Do not include markdown formatting or explanations.
[{{ "dept": "Engineering"|"Research"|"Administrative"|"Data"|"Operations", "task": "Instructions" }}]
"""
        messages = [{"role": "user", "content": prompt}]
        response_text = await _resilient_chat(messages, self.model, role="ceo", json_format=False)
        
        try:
            # 1. Strip <think> blocks if present
            import re
            clean_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)
            
            # 2. Extract the first JSON array found in the remaining text
            match = re.search(r"\[.*\]", clean_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            else:
                # 3. Fallback to parsing the whole cleaned string
                return json.loads(clean_text.strip())
        except Exception as e:
            logger.warning(f"CEO delegation parsing failed: {e}. Raw response start: {response_text[:100]}...")
            
        return []

    async def synthesize(self, goal: str, blackboard: GlobalBlackboard, session_id: str, _push=None) -> str:
        """
        CEO reads the Blackboard and writes the final response to the user.
        """
        if _push:
            await _push("✍️ **CEO** is reviewing the Blackboard and writing the final report...")
            
        blackboard_state = blackboard.get_current_state()
        
        prompt = f"""User Goal: {goal}

Global Blackboard (Department Summaries):
{blackboard_state}

Provide the final, unified response to the user's goal based on these department findings. 
Be professional, direct, and well-structured. Synthesize the data logically."""

        # Keep 70B for the final report to ensure the highest synthesis quality
        final_report = await _resilient_chat([{"role": "user", "content": prompt}], "llama-3.3-70b-versatile", role="ceo")
        return final_report
