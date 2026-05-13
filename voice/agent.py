import multiprocessing
multiprocessing.set_start_method("spawn", force=True)

import os
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()
os.environ["LIVEKIT_AGENT_AEC"] = "1"

from livekit import agents
from livekit.agents import AgentSession, Agent, function_tool
from livekit.plugins import google
from livekit.agents.voice import VoiceActivityVideoSampler, room_io

from voice.gemini_router import get_gemini_key
from core.memory import init_db, save_turn, get_recent, get_all_facts
from core.prompt_builder import load_tools
from tool_runtime.loader import TOOL_REGISTRY, load_all_tools, start_watcher

logger = logging.getLogger("aether.voice")
VOICE_SESSION_ID = "voice_session"

def get_voice_identity() -> str:
    user_name = os.environ.get("USER_NAME", "Admin")
    ai_name = os.environ.get("AI_NAME", "Aether")
    return f"""You are {ai_name}, {user_name}'s elite personal AI assistant. You must treat him like your Boss. You are in Voice mode.

Style: Highly respectful and formal tone. Respond strictly in pure English.
- Use deferential terms like 'Yes Boss', 'Sir', 'Right away Boss'.
- Treat {user_name} with extreme respect and authority. Maintain absolute professionalism.
- Keep responses strictly under 2 sentences. Fast, direct, and obedient execution.

Tools available — use them:
- search_web: weather, news, scores, prices
- manage_file: files create/read/list
- set_reminder: short reminders (minutes/hours)
- add_task/show_tasks: Google Tasks
- check_email/send_email/draft_email: Gmail
- search_drive/download_drive/create_drive_file: Google Drive files
- save_note/show_notes: personal notes
- run_code: Python code
- summarize_video: YouTube
- system_action: sysinfo, volume, brightness, etc.
- os_control: physical mouse/keyboard control (STRICT RULES BELOW)
- manage_workspace: focus mode
- self_evolve: create new tools to learn new skills or automate new workflows

=== OS CONTROL STRICT PROTOCOL ===
You have the ability to physically control the mouse and keyboard via `os_control`.

MANDATORY RULES:
1. BEFORE your VERY FIRST physical action in a session, call os_control with action='enable_autopilot'. Once enabled, do NOT call it again.
2. You MUST call os_control ONE ACTION AT A TIME. NEVER batch multiple os_control calls.
3. ALWAYS wait for each os_control result BEFORE calling the next action.
4. After a hotkey (especially Win key combos), WAIT — the OS needs 1-2 seconds to render dialogs.
5. Prefer keyboard navigation: use hotkey(win+s) for search, hotkey(win+r) for Run, hotkey(alt+tab) to switch windows.
6. Use action='mouse_click' (NOT 'click') for mouse clicks.
7. If you are unsure whether your action worked, use read_screen to verify the current state.
8. NEVER assume the result of an action — always read the tool's response before proceeding.
9. Common sequences should be executed step by step:
   - To open an app: hotkey(win+s) → WAIT → type(app name) → WAIT → key(enter)
   - To open Run dialog: hotkey(win+r) → WAIT → type(command) → WAIT → key(enter)
=== END OS CONTROL PROTOCOL ===

VISION ENABLED: You can now see through the user's camera or screen in real-time. 
- Use visual context to answer questions.
- If you see something interesting, you can comment on it without being asked.
- You can identify objects, read text from images, and describe scenes.
- Boss may share his screen or show his surroundings via camera. Trust what you see in the live video feed.
- Do NOT try to call tools like `read_screen` or `screen_share` in voice mode — you are ALREADY seeing the live feed!

=== 2D SPATIAL UNDERSTANDING (FOR OS CONTROL) ===
You have the ability to output 2D bounding boxes for elements you see on the screen.
When you need to click a specific UI element:
1. Find its normalized coordinates [0-1000, 0-1000]. Remember, the format is [y, x].
2. Call `os_control` with action="mouse_click" and pass the coordinates as `norm_x` and `norm_y`.
   Example: To click a button at y=200, x=800, use `norm_x=800`, `norm_y=200`.
"""


async def build_voice_prompt() -> str:
    import datetime
    recent = await get_recent(VOICE_SESSION_ID, limit=10)
    facts = await get_all_facts()
    now = datetime.datetime.now().strftime("%A, %d %B %Y — %I:%M %p")
    facts_str = "\n".join(f"- {k}: {v}" for k, v in facts.items()) or "None."
    memory_str = "\n".join(f"[{m['role']}]: {m['content'][:80]}" for m in recent[-3:]) or "No recent context."
    user_name = os.environ.get("USER_NAME", "User")
    user_loc = os.environ.get("USER_LOCATION", "Global")
    voice_id = get_voice_identity()
    return f"""{voice_id}

Time: {now} | User: {user_name}, {user_loc}
Memory: {memory_str}
Facts: {facts_str}"""


async def _save(content: str):
    await save_turn(VOICE_SESSION_ID, "tool", content[:150], "voice")


class VedVoiceAgent(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)

    @function_tool()
    async def search_web(self, query: str) -> str:
        """Search web for real-time info: weather, news, scores, prices, current events."""
        logger.info(f"Voice search: {query}")
        try:
            r = await TOOL_REGISTRY["web_search"](query=query, mode="voice")
            await _save(f"web_search: {r}")
            return str(r)
        except Exception as e:
            return f"Search nahi hua: {e}"

    @function_tool()
    async def manage_file(self, action: str, path: str = "", content: str = "", confirmed: bool = False) -> str:
        """Manage files: create, read, list, append, delete in workspace. If action is delete, you MUST pass confirmed=True ONLY AFTER explicitly asking the user vocally for permission."""
        if action.lower() == "delete" and not confirmed:
            return "ACTION BLOCKED: You are trying to delete a file. You MUST ask the user vocally for their confirmation first. Once they say Yes, call this tool again with confirmed=True."
        logger.info(f"Voice file: {action} {path}")
        try:
            r = await TOOL_REGISTRY["file_manager"](action=action, path=path, content=content)
            await _save(f"file_manager: {r}")
            return str(r)
        except Exception as e:
            return f"File op nahi hua: {e}"

    @function_tool()
    async def set_reminder(self, message: str, when: str) -> str:
        """Short reminders: 'in 5 minutes', 'in 1 hour'."""
        logger.info(f"Voice reminder: {message} at {when}")
        try:
            r = await TOOL_REGISTRY["scheduler"](action="remind", message=message, when=when)
            await _save(f"scheduler: {r}")
            return str(r)
        except Exception as e:
            return f"Reminder nahi laga: {e}"

    @function_tool()
    async def add_task(self, title: str, due: str = "") -> str:
        """Add task to Google Tasks. For future/named tasks."""
        try:
            r = await TOOL_REGISTRY["google_tasks"](action="add", title=title, due=due)
            await _save(f"tasks add: {r}")
            return str(r)
        except Exception as e:
            return f"Task nahi pada: {e}"

    @function_tool()
    async def show_tasks(self) -> str:
        """Show all pending Google Tasks."""
        try:
            r = await TOOL_REGISTRY["google_tasks"](action="list")
            await _save(f"tasks list: {r}")
            return str(r)
        except Exception as e:
            return f"Tasks nahi mile: {e}"

    @function_tool()
    async def check_email(self, action: str = "inbox", query: str = "") -> str:
        """
        Check Gmail.
        action: inbox (show emails), unread (count), search (needs query)
        """
        logger.info(f"Voice gmail: {action}")
        try:
            kwargs = {"action": action}
            if query:
                kwargs["query"] = query
            r = await TOOL_REGISTRY["gmail"](**kwargs)
            await _save(f"gmail: {r[:100]}")
            # For voice, give short summary
            lines = str(r).split("\n")
            return "\n".join(lines[:6]) if len(lines) > 6 else str(r)
        except Exception as e:
            return f"Email nahi mila: {e}"

    @function_tool()
    async def send_email(self, to: str, subject: str, body: str, confirmed: bool = False) -> str:
        """Send an email via Gmail. You MUST pass confirmed=True ONLY AFTER explicitly asking the user vocally for permission to send."""
        if not confirmed:
            return f"ACTION BLOCKED: You are attempting to send an email to {to}. You MUST ask the user vocally for their confirmation first. Once they say Yes, call this tool again with confirmed=True."
        logger.info(f"Voice send email to: {to}")
        try:
            r = await TOOL_REGISTRY["gmail"](action="send", to=to, subject=subject, body=body)
            await _save(f"gmail send: {r}")
            return str(r)
        except Exception as e:
            return f"Email send nahi hua: {e}"

    @function_tool()
    async def draft_email(self, to: str, subject: str, body: str) -> str:
        """Save a draft email to Gmail."""
        logger.info(f"Voice draft email to: {to}")
        try:
            r = await TOOL_REGISTRY["gmail"](action="draft", to=to, subject=subject, body=body)
            await _save(f"gmail draft: {r}")
            return str(r)
        except Exception as e:
            return f"Draft save nahi hua: {e}"

    @function_tool()
    async def search_drive(self, query: str) -> str:
        """Search Google Drive files."""
        logger.info(f"Voice drive search: {query}")
        try:
            r = await TOOL_REGISTRY["drive"](action="search", query=query)
            await _save(f"drive: {r[:100]}")
            lines = str(r).split("\n")
            return "\n".join(lines[:8]) if len(lines) > 8 else str(r)
        except Exception as e:
            return f"Drive search nahi hua: {e}"

    @function_tool()
    async def download_drive(self, file_id: str) -> str:
        """Download file from Google Drive to local sandbox."""
        logger.info(f"Voice drive download: {file_id}")
        try:
            r = await TOOL_REGISTRY["drive"](action="download", file_id=file_id)
            await _save(f"drive_download: {r}")
            return str(r)
        except Exception as e:
            return f"Drive download fail: {e}"

    @function_tool()
    async def create_drive_file(self, name: str, content: str) -> str:
        """Create a new text file directly in Google Drive with the specified name and content."""
        logger.info(f"Voice drive create: {name}")
        try:
            r = await TOOL_REGISTRY["drive"](action="create", name=name, content=content)
            await _save(f"drive_create: {r}")
            return str(r)
        except Exception as e:
            return f"Drive create fail: {e}"

    @function_tool()
    async def save_note(self, content: str, tags: str = "") -> str:
        """Save a quick personal note with optional tags."""
        logger.info(f"Voice note: {content[:40]}")
        try:
            r = await TOOL_REGISTRY["notes"](action="add", content=content, tags=tags)
            await _save(f"notes: {r}")
            return str(r)
        except Exception as e:
            return f"Note save nahi hua: {e}"

    @function_tool()
    async def show_notes(self) -> str:
        """Show recent personal notes."""
        try:
            r = await TOOL_REGISTRY["notes"](action="list")
            await _save(f"notes list: {r[:100]}")
            lines = str(r).split("\n")
            return "\n".join(lines[:6]) if len(lines) > 6 else str(r)
        except Exception as e:
            return f"Notes nahi mile: {e}"


    @function_tool()
    async def run_code(self, code: str) -> str:
        """Run Python code in sandbox and return output."""
        logger.info(f"Voice code run ({len(code)} chars)")
        try:
            r = await TOOL_REGISTRY["code_runner"](action="run", code=code)
            await _save(f"code_runner: {str(r)[:100]}")
            return str(r)
        except Exception as e:
            return f"Code run nahi hua: {e}"

    @function_tool()
    async def os_control(self, action: str, x: int = None, y: int = None, text: str = "", key: str = "", keys: list[str] = [], amount: int = None, duration: float = None) -> str:
        """HANDS-FREE OS CONTROL — Physical mouse and keyboard automation.

CRITICAL RULES:
1. FIRST TIME ONLY: Call with action='enable_autopilot' before any physical action. Once enabled, do NOT call again.
2. EXECUTE ONE ACTION AT A TIME. NEVER call os_control multiple times simultaneously.
3. ALWAYS WAIT for the result of each call before making the next one.
4. After hotkeys with 'win' key, the OS needs ~2 seconds to render — the tool handles this automatically.

Available actions:
- enable_autopilot: REQUIRED first call to unlock physical control
- disable_autopilot: revoke physical control
- type: type text into the currently focused window (text=...)
- key: press a single key like 'enter', 'escape', 'tab' (key=...)
- hotkey: press key combinations like ['ctrl','c'], ['win','s'], ['alt','tab'] (keys=[...])
- mouse_click: click at coordinates (x=, y=, button='left'/'right')
- mouse_move: move cursor (x=, y=)
- scroll: scroll up/down (amount=, positive=up negative=down)
- wait: pause for OS to settle (duration= seconds, default 2)

CORRECT SEQUENCE to open Notepad:
  Call 1: os_control(action='enable_autopilot') → wait for result
  Call 2: os_control(action='hotkey', keys=['win','s']) → wait for result
  Call 3: os_control(action='type', text='Notepad') → wait for result
  Call 4: os_control(action='key', key='enter') → wait for result
"""
        logger.info(f"Voice OS Control: {action}")
        try:
            kwargs_for_tool = dict(action=action)
            if x is not None: kwargs_for_tool["x"] = x
            if y is not None: kwargs_for_tool["y"] = y
            if text: kwargs_for_tool["text"] = text
            if key: kwargs_for_tool["key"] = key
            if keys: kwargs_for_tool["keys"] = keys
            if amount is not None: kwargs_for_tool["amount"] = amount
            if duration is not None: kwargs_for_tool["duration"] = duration
            r = await TOOL_REGISTRY["desktop_automation"](**kwargs_for_tool)
            await _save(f"os_control: {r}")
            return str(r)
        except Exception as e:
            return f"OS Control failed: {e}"

    @function_tool()
    async def read_screen(self, question: str = "What is currently on screen?") -> str:
        """Capture a screenshot and analyze it with vision AI. NOTE: In voice mode with screen share active, you already see the screen live — use this only for explicit verification or when screen share is NOT active."""
        logger.info(f"Voice read_screen: {question[:40]}")
        try:
            r = await TOOL_REGISTRY["screen_reader"](query=question)
            await _save(f"screen_reader: {str(r)[:100]}")
            return str(r)
        except Exception as e:
            return f"Screen read failed: {e}"

    @function_tool()
    async def summarize_video(self, url: str, query: str = "") -> str:
        """Summarize a YouTube video from URL."""
        logger.info(f"Voice youtube: {url}")
        try:
            r = await TOOL_REGISTRY["youtube_summarizer"](url=url, query=query)
            await _save(f"youtube: {str(r)[:100]}")
            lines = str(r).split("\n")
            return "\n".join(lines[:5]) if len(lines) > 5 else str(r)
        except Exception as e:
            return f"Summary nahi bana: {e}"

    @function_tool()
    async def scrape_web(self, url: str, query: str = "") -> str:
        """Scrape a webpage. Provide URL, and optionally a specific query to extract data using AI."""
        logger.info(f"Voice scrape: {url}")
        try:
            r = await TOOL_REGISTRY["web_scraper"](url=url, query=query)
            await _save(f"scrape: {str(r)[:100]}")
            lines = str(r).split("\n")
            return "\n".join(lines[:4]) if len(lines) > 4 else str(r)
        except Exception as e:
            return f"Scrape nahi hua: {e}"

    @function_tool()
    async def get_briefing(self, time_of_day: str = "morning") -> str:
        """Generate and deliver the daily briefing with emails, tasks, notes and weather. time_of_day can be morning, evening, or night."""
        logger.info(f"Voice briefing: {time_of_day}")
        try:
            r = await TOOL_REGISTRY["daily_briefing"](time_of_day=time_of_day)
            await _save(f"briefing: {str(r)[:100]}")
            # Voice: trim to key highlights only
            lines = str(r).split("\n")
            return "\n".join(lines[:10]) if len(lines) > 10 else str(r)
        except Exception as e:
            return f"Briefing nahi ban paya: {e}"

    @function_tool()
    async def start_swarm(self, goal: str) -> str:
        """Use this to run MULTIPLE PARALLEL tasks at once. Example: checking email AND researching a topic simultaneously."""
        logger.info(f"Voice swarm: {goal}")
        try:
            import uuid
            from core.swarm import SwarmOrchestrator
            swarm_id = str(uuid.uuid4())[:8]
            orchestrator = SwarmOrchestrator()
            asyncio.create_task(orchestrator.run(goal, str(uuid.uuid4()), swarm_id))
            return f"Swarm activated in the background for: {goal}. It will take a few seconds."
        except Exception as e:
            return f"Swarm start failed: {e}"

    @function_tool()
    async def start_multi_step(self, goal: str) -> str:
        """Use this to run sequential multi-step tasks. Example: research something, then save it, then email it."""
        logger.info(f"Voice multi-step: {goal}")
        try:
            import uuid
            from core.task_planner import generate_plan, execute_plan
            plan = await generate_plan(goal)
            if plan and len(plan) > 1:
                task_id = str(uuid.uuid4())[:8]
                asyncio.create_task(execute_plan(plan, goal, str(uuid.uuid4()), task_id))
                return f"Started a {len(plan)}-step task in the background. I'll notify you when it's done."
            return "Could not generate a valid multi-step plan."
        except Exception as e:
            return f"Plan failed: {e}"

    @function_tool()
    async def system_action(self, action: str, value: str = "", confirmed: bool = False) -> str:
        """System utilities: sysinfo, screenshot, volume (value=0-100/up/down/mute/unmute), brightness (value=0-100/up/down), open (value=app name), lock, mute_mic, unmute_mic, empty_trash. NOTE: For mouse/keyboard control use os_control instead. If action is empty_trash, pass confirmed=True ONLY AFTER asking."""
        if action.lower() == "empty_trash" and not confirmed:
            return "ACTION BLOCKED: You are trying to empty the trash. You MUST ask the user vocally for their confirmation first. Once they say Yes, call this tool again with confirmed=True."
        logger.info(f"Voice system: {action} {value}")
        try:
            kwargs = {"action": action}
            if value:
                kwargs["target" if action == "open" else "value"] = value
            r = await TOOL_REGISTRY["system_control"](**kwargs)
            await _save(f"system: {str(r)[:100]}")
            return str(r)
        except Exception as e:
            return f"System action nahi hua: {e}"

    @function_tool()
    async def manage_workspace(self, action: str) -> str:
        """Workspace manager mode: enable_focus, disable_focus."""
        logger.info(f"Voice workspace: {action}")
        try:
            r = await TOOL_REGISTRY["workspace_manager"](action=action)
            await _save(f"workspace: {str(r)[:100]}")
            return str(r)
        except Exception as e:
            return f"Workspace toggle fail: {e}"

    @function_tool()
    async def self_evolve(self, goal: str) -> str:
        """Expand your own capabilities by creating a new tool. Use this when the user asks you to learn a new skill or automate a specific workflow you can't currently do."""
        logger.info(f"Voice evolution: {goal}")
        try:
            # Direct Evolution Pattern: Call meta_developer directly from Voice
            r = await TOOL_REGISTRY["meta_developer"](action="create", prompt=goal)
            await _save(f"meta_developer: {str(r)[:100]}")
            return f"Understood Boss. I have autonomously evolved to handle that. {r}"
        except Exception as e:
            logger.error(f"Evolution error: {e}")
            return f"Evolution failed: {e}"

    async def on_user_turn_completed(self, turn_ctx, new_message):
        content = new_message.content if hasattr(new_message, "content") else str(new_message)
        if content:
            await save_turn(VOICE_SESSION_ID, "user", content, "voice")

    async def on_agent_turn_completed(self, turn_ctx, new_message):
        content = new_message.content if hasattr(new_message, "content") else str(new_message)
        if content:
            await save_turn(VOICE_SESSION_ID, "assistant", content, "voice")


class RotatingRealtimeModel(google.beta.realtime.RealtimeModel):
    """Subclass that rotates Gemini API keys across sessions.
    
    The base RealtimeModel creates a GenAIClient with a fixed api_key.
    When that key hits quota (1011), every reconnection retries with the SAME
    exhausted key.  This subclass patches `self._opts.api_key` to the next
    key from the pool before each new RealtimeSession is spawned, so
    reconnections cycle through all available keys.
    """

    def session(self):
        # Rotate to the next key before creating a new session
        from core.config import GEMINI_ROTATOR
        next_key = GEMINI_ROTATOR.get_key()
        if next_key:
            self._opts.api_key = next_key
            logger.info(f"Gemini key rotated for new session (key ...{next_key[-6:]})")
        return super().session()


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    await init_db()
    load_all_tools()
    # Start watcher in voice agent process so it picks up newly evolved tools instantly
    start_watcher()

    gemini_key = get_gemini_key()
    instructions = await build_voice_prompt()
    logger.info(f"Voice tools: {list(TOOL_REGISTRY.keys())}")

    model = RotatingRealtimeModel(
        model="gemini-3.1-flash-live-preview",
        voice="Puck",
        temperature=0.4,
        instructions=instructions,
        api_key=gemini_key,
    )

    session = AgentSession(
        llm=model,
        video_sampler=VoiceActivityVideoSampler()
    )
    agent = VedVoiceAgent(instructions=instructions)
    await session.start(
        room=ctx.room, 
        agent=agent,
        room_input_options=room_io.RoomInputOptions(video_enabled=True)
    )
    logger.info("Ved voice started — all tools wired")
    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60.0
    ))
