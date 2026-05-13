"""
System control tool — open apps/files, get system info,
control volume/brightness, take screenshots, lock, empty trash, toggle mic.

NOTE: Keyboard/mouse control is handled EXCLUSIVELY by desktop_automation.py.
      This tool does NOT provide any keyboard/mouse actions.
"""

import os
import subprocess
import platform
import logging
import asyncio
from datetime import datetime

TOOL_NAME = "system_control"
TOOL_DESCRIPTION = "Control system: open apps, sysinfo, volume, brightness, screenshot, lock, empty_trash, mute_mic, unmute_mic"

logger = logging.getLogger("aether.tools.system_control")

# ── Pre-cached platform check (called hundreds of times) ──────────────────────
_IS_WINDOWS = platform.system() == "Windows"

# ── Lazy-loaded heavy modules ─────────────────────────────────────────────────
_psutil = None
_pycaw_cache = None  # (AudioUtilities, IAudioEndpointVolume, CLSCTX_ALL, cast, POINTER)


def _get_psutil():
    global _psutil
    if _psutil is None:
        import psutil
        _psutil = psutil
    return _psutil


def _get_pycaw():
    """Lazy-load and cache all pycaw/comtypes objects (expensive COM init)."""
    global _pycaw_cache
    if _pycaw_cache is None:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        _pycaw_cache = (AudioUtilities, IAudioEndpointVolume, CLSCTX_ALL, cast, POINTER)
    return _pycaw_cache


async def run(**kwargs) -> str:
    action = kwargs.get("action", "").lower().strip()
    target = str(kwargs.get("target") or kwargs.get("app") or kwargs.get("file") or kwargs.get("name") or kwargs.get("path") or "")
    value = str(kwargs.get("value") or kwargs.get("level") or kwargs.get("amount") or "")

    # ── Open app or file ──────────────────────────────────────────────────────
    if action == "open":
        if not target:
            return "Please specify what to open."
        try:
            def _open():
                if _IS_WINDOWS:
                    os.startfile(target)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", target])
                else:
                    subprocess.Popen(["xdg-open", target])
            await asyncio.to_thread(_open)
            return f"Opened: {target}"
        except Exception as e:
            return f"Could not open '{target}': {e}"

    # ── System info (fast — no blocking interval) ─────────────────────────────
    elif action == "sysinfo":
        try:
            psutil = _get_psutil()
        except ImportError:
            return "psutil not installed. Run: pip install psutil"
        try:
            def _get_sysinfo():
                # Use interval=0 for instant non-blocking CPU read
                # (returns CPU since last call, or 0.0 on first call)
                cpu = psutil.cpu_percent(interval=0)
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage('/' if not _IS_WINDOWS else 'C:\\')
                battery = psutil.sensors_battery()

                info = [
                    f"CPU: {cpu}%",
                    f"RAM: {ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB ({ram.percent}%)",
                    f"Disk: {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)",
                ]
                if battery:
                    plugged = "plugged" if battery.power_plugged else "battery"
                    info.append(f"Battery: {battery.percent:.0f}% ({plugged})")
                return "\n".join(info)

            return await asyncio.to_thread(_get_sysinfo)
        except Exception as e:
            return f"System info error: {e}"

    # ── Volume ────────────────────────────────────────────────────────────────
    elif action == "volume":
        if not value:
            return "Specify value: 0-100, 'up', 'down', 'mute', or 'unmute'"
        try:
            if _IS_WINDOWS:
                def _set_volume():
                    AudioUtilities, IAudioEndpointVolume, CLSCTX_ALL, cast, POINTER = _get_pycaw()
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    vol = cast(interface, POINTER(IAudioEndpointVolume))

                    if value == "mute":
                        vol.SetMute(1, None)
                        return "Volume muted."
                    elif value == "unmute":
                        vol.SetMute(0, None)
                        return "Volume unmuted."
                    elif value == "up":
                        current = vol.GetMasterVolumeLevelScalar()
                        new = min(1.0, current + 0.1)
                        vol.SetMasterVolumeLevelScalar(new, None)
                        return f"Volume: {int(new * 100)}%."
                    elif value == "down":
                        current = vol.GetMasterVolumeLevelScalar()
                        new = max(0.0, current - 0.1)
                        vol.SetMasterVolumeLevelScalar(new, None)
                        return f"Volume: {int(new * 100)}%."
                    else:
                        level = max(0, min(100, int(value))) / 100.0
                        vol.SetMasterVolumeLevelScalar(level, None)
                        return f"Volume set to {int(level * 100)}%."

                return await asyncio.to_thread(_set_volume)
            else:
                await asyncio.to_thread(
                    subprocess.run, ["amixer", "sset", "Master", f"{value}%"],
                    capture_output=True
                )
                return f"Volume set to {value}%."
        except ImportError:
            return "Volume control requires pycaw and comtypes. Run: pip install pycaw comtypes"
        except Exception as e:
            return f"Volume control error: {e}"

    # ── Brightness ────────────────────────────────────────────────────────────
    elif action == "brightness":
        if not value:
            return "Specify value: 0-100, 'up', or 'down'"
        try:
            def _set_brightness():
                import screen_brightness_control as sbc
                current = sbc.get_brightness()[0]
                if value == "up":
                    new_val = min(100, current + 10)
                elif value == "down":
                    new_val = max(0, current - 10)
                else:
                    new_val = max(0, min(100, int(value)))
                sbc.set_brightness(new_val)
                return f"Brightness: {new_val}%."

            return await asyncio.to_thread(_set_brightness)
        except ImportError:
            return "Brightness control requires screen-brightness-control. Run: pip install screen-brightness-control (laptops only)."
        except Exception as e:
            return f"Brightness error: {e}"

    # ── Screenshot (JPEG for speed — 3-5x faster than PNG) ────────────────────
    elif action == "screenshot":
        try:
            from PIL import ImageGrab
            from core.config import get_workspace

            def _take_screenshot():
                save_dir = get_workspace() / "screenshots"
                save_dir.mkdir(parents=True, exist_ok=True)
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                path = save_dir / filename
                img = ImageGrab.grab()
                # JPEG is 3-5x faster to save than PNG
                img = img.convert("RGB") if img.mode != "RGB" else img
                img.save(str(path), format="JPEG", quality=80)
                return f"Screenshot saved: {path}"

            return await asyncio.to_thread(_take_screenshot)
        except ImportError:
            return "Screenshot requires Pillow. Run: pip install Pillow"
        except Exception as e:
            return f"Screenshot error: {e}"

    # ── Lock workstation ──────────────────────────────────────────────────────
    elif action == "lock":
        if _IS_WINDOWS:
            try:
                import ctypes
                await asyncio.to_thread(ctypes.windll.user32.LockWorkStation)
                return "Workstation locked."
            except Exception as e:
                return f"Lock failed: {e}"
        else:
            return "Locking only supported on Windows."

    # ── Empty trash ───────────────────────────────────────────────────────────
    elif action == "empty_trash":
        if _IS_WINDOWS:
            try:
                import ctypes
                def _empty():
                    return ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
                result = await asyncio.to_thread(_empty)
                return "Recycle Bin emptied." if result == 0 else f"Empty trash code {result}."
            except Exception as e:
                return f"Empty trash failed: {e}"
        else:
            return "Empty trash only supported on Windows."

    # ── Microphone mute/unmute ────────────────────────────────────────────────
    elif action in ["mute_mic", "unmute_mic"]:
        if _IS_WINDOWS:
            try:
                def _toggle_mic():
                    from ctypes import cast, POINTER
                    from comtypes import CLSCTX_ALL
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    import comtypes

                    deviceEnumerator = comtypes.CoCreateInstance(
                        AudioUtilities.CLSID_MMDeviceEnumerator,
                        AudioUtilities.IMMDeviceEnumerator,
                        comtypes.CLSCTX_INPROC_SERVER
                    )
                    try:
                        mic_device = deviceEnumerator.GetDefaultAudioEndpoint(1, 0)
                    except Exception:
                        return "No microphone found."

                    interface = mic_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    mic_vol = cast(interface, POINTER(IAudioEndpointVolume))

                    mute_val = 1 if action == "mute_mic" else 0
                    mic_vol.SetMute(mute_val, None)
                    return "Mic MUTED." if mute_val else "Mic UNMUTED."

                return await asyncio.to_thread(_toggle_mic)
            except ImportError:
                return "Mic control requires pycaw and comtypes. Run: pip install pycaw comtypes"
            except Exception as e:
                return f"Mic toggle error: {e}"
        else:
            try:
                await asyncio.to_thread(
                    subprocess.run, ["amixer", "set", "Capture", "toggle"],
                    capture_output=True
                )
                return f"Mic {'muted' if action == 'mute_mic' else 'unmuted'}."
            except Exception as e:
                return f"Mic toggle error: {e}"

    else:
        return (
            f"Unknown action: '{action}'. "
            "Available: open, sysinfo, volume, brightness, screenshot, "
            "lock, empty_trash, mute_mic, unmute_mic"
        )
