"""
Desktop Automation tool — provides hands-free OS control via PyAutoGUI.
Includes a safety gate that requires explicitly enabling autopilot first.

Features:
  - Global asyncio.Lock to serialize all OS actions (prevents race conditions)
  - Minimal delays tuned for speed — only what the OS truly needs
  - Rich feedback messages to guide the LLM's next action
"""

import time
import logging
import asyncio

TOOL_NAME = "desktop_automation"
TOOL_DESCRIPTION = "Hands-free OS control: click, type, press keys, hotkeys, scroll. Requires enabling autopilot first."

logger = logging.getLogger("aether.tools.desktop_automation")

# ── Safety Gate ───────────────────────────────────────────────────────────────
_autopilot_enabled = False

# ── Serialization Lock ────────────────────────────────────────────────────────
_action_lock = asyncio.Lock()
_last_action_time: float = 0.0
_COOLDOWN_MS = 120  # Minimum ms between actions (just enough to prevent OS race)

# ── Per-action settle delays (seconds) — tuned for speed ──────────────────────
_ACTION_DELAYS = {
    "enable_autopilot": 0.0,
    "disable_autopilot": 0.0,
    "mouse_move": 0.05,
    "move": 0.05,
    "mouse_click": 0.25,
    "click": 0.25,
    "mouse_drag": 0.2,
    "drag": 0.2,
    "type_text": 0.1,
    "type": 0.1,
    "press_key": 0.15,
    "press": 0.15,
    "key": 0.15,
    "hotkey": 0.3,
    "scroll": 0.1,
    "wait": 0.0,
}

# Lazy-loaded PyAutoGUI reference (import once, reuse forever)
_pyautogui = None


def _get_pyautogui():
    global _pyautogui
    if _pyautogui is None:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.03  # Global pause between pyautogui calls (default 0.1)
        _pyautogui = pyautogui
    return _pyautogui


def _require_autopilot() -> str | None:
    if not _autopilot_enabled:
        return "ACTION BLOCKED: Autopilot is disabled. You must call os_control with action='enable_autopilot' first and ask the user for permission."
    return None


async def run(**kwargs) -> str:
    global _autopilot_enabled, _last_action_time
    action = kwargs.get("action", "").lower().strip()

    # ── Enable/Disable Safety Gate (no lock needed) ───────────────────────
    if action == "enable_autopilot":
        _autopilot_enabled = True
        logger.warning("Autopilot ENABLED by user.")
        return "Autopilot enabled. You now have full physical control over the mouse and keyboard. IMPORTANT: Execute actions ONE AT A TIME. Wait for each result before calling the next action."

    elif action == "disable_autopilot":
        _autopilot_enabled = False
        logger.info("Autopilot DISABLED.")
        return "Autopilot disabled. Physical control revoked."

    # ── For all physical actions, verify the safety gate ──────────────────
    err = _require_autopilot()
    if err:
        return err

    # ── Cooldown check — reject rapid-fire parallel calls ─────────────────
    now_ms = time.monotonic() * 1000
    elapsed = now_ms - (_last_action_time * 1000) if _last_action_time else _COOLDOWN_MS + 1
    if elapsed < _COOLDOWN_MS:
        wait_ms = int(_COOLDOWN_MS - elapsed)
        return f"ACTION THROTTLED: Previous action is still settling. Please wait {wait_ms}ms before sending the next action. Do NOT batch multiple os_control calls."

    # ── Acquire the global lock so actions execute one at a time ───────────
    async with _action_lock:
        try:
            pag = _get_pyautogui()
        except ImportError:
            return "Error: pyautogui is not installed. Please run 'pip install pyautogui'."

        def _execute_sync():
            if action in ["mouse_move", "move", "mouse_click", "click", "mouse_drag", "drag"]:
                x = kwargs.get("x")
                y = kwargs.get("y")
                
                # Check for normalized coordinates [0-1000] from Gemini
                norm_x = kwargs.get("norm_x")
                norm_y = kwargs.get("norm_y")
                
                if norm_x is not None and norm_y is not None:
                    screen_width, screen_height = pag.size()
                    # Gemini coordinates are sometimes [y, x] or [x, y], typically 0-1000.
                    # We assume norm_x and norm_y are 0-1000.
                    x = int((float(norm_x) / 1000.0) * screen_width)
                    y = int((float(norm_y) / 1000.0) * screen_height)

                if action in ["mouse_move", "move"]:
                    if x is None or y is None:
                        return "Error: x and y (or norm_x, norm_y) coordinates are required for mouse_move."
                    pag.moveTo(int(x), int(y), duration=0.08)
                    return f"Mouse moved to ({x}, {y})."

                elif action in ["mouse_click", "click"]:
                    button = kwargs.get("button", "left")
                    clicks = kwargs.get("clicks", 1)

                    if x is not None and y is not None:
                        pag.click(x=int(x), y=int(y), button=button, clicks=int(clicks))
                        return f"Clicked {button} at ({x}, {y})."
                    else:
                        pag.click(button=button, clicks=int(clicks))
                        return f"Clicked {button} at current cursor position."

                elif action in ["mouse_drag", "drag"]:
                    if x is None or y is None:
                        return "Error: x and y coordinates are required for mouse_drag."
                    pag.dragTo(int(x), int(y), duration=0.3)
                    return f"Mouse dragged to ({x}, {y})."

            elif action in ["type_text", "type"]:
                text = kwargs.get("text", "")
                press_enter = kwargs.get("press_enter", False)
                if not text:
                    return "Error: text parameter is required for type action."

                # Always use clipboard paste — it's faster AND handles Unicode
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    pag.hotkey('ctrl', 'v')
                except ImportError:
                    # Fallback: pyautogui.write for ASCII
                    try:
                        text.encode('ascii')
                        pag.write(text, interval=0.01)
                    except UnicodeEncodeError:
                        return "Install pyperclip for Unicode text support: pip install pyperclip"

                if press_enter:
                    pag.press("enter")
                return f"Typed: \"{text[:50]}{'...' if len(text) > 50 else ''}\"."

            elif action in ["press_key", "press", "key"]:
                key = kwargs.get("key", "").lower()
                if not key:
                    return "Error: key parameter is required for press_key action."
                pag.press(key)
                return f"Pressed key: {key}."

            elif action == "hotkey":
                keys = kwargs.get("keys", [])
                if not keys or not isinstance(keys, list):
                    return "Error: keys parameter must be a list of strings (e.g. ['ctrl', 'c'])."
                pag.hotkey(*keys)
                combo = " + ".join(keys)
                return f"Executed hotkey: {combo}."

            elif action == "scroll":
                amount = kwargs.get("amount")
                if amount is None:
                    return "Error: amount parameter is required for scroll (positive = up, negative = down)."
                pag.scroll(int(amount))
                return f"Scrolled by {amount}."

            elif action == "wait":
                return "Waited for the OS to settle."

            elif action == "get_cursor":
                pos = pag.position()
                return f"Cursor is at ({pos.x}, {pos.y})."

            else:
                return (
                    f"Unknown action: '{action}'. Available actions:\n"
                    "- enable_autopilot / disable_autopilot\n"
                    "- mouse_move (x, y) / mouse_click (x, y, button) / mouse_drag (x, y)\n"
                    "- type (text, press_enter) / key (key) / hotkey (keys[])\n"
                    "- scroll (amount) / wait (duration) / get_cursor"
                )

        try:
            result = await asyncio.to_thread(_execute_sync)

            # Minimal delay: just enough for the OS to register the action
            if action == "wait":
                duration = float(kwargs.get("duration", 1.0))
                duration = min(max(duration, 0.3), 10.0)
                await asyncio.sleep(duration)
            else:
                delay = _ACTION_DELAYS.get(action, 0.1)
                # Extra delay only for Win key hotkeys — OS dialogs genuinely need it
                if action == "hotkey" and "win" in [k.lower() for k in kwargs.get("keys", [])]:
                    delay = 0.8
                await asyncio.sleep(delay)

            _last_action_time = time.monotonic()
            return result

        except Exception as e:
            logger.error(f"Desktop automation error: {e}")
            return f"Automation failed: {e}"
