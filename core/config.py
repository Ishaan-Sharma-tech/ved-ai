import os
import itertools
import shutil
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values
import platform
import ctypes

# ── Windows DPI Awareness ─────────────────────────────────────────────────────
# Fixes mouse alignment issues on High DPI displays for PyAutoGUI and ImageGrab
if platform.system() == "Windows":
    try:
        # 1 = PROCESS_SYSTEM_DPI_AWARE, 2 = PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Find the .env file in the project root
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
ENV_FILE = PROJECT_ROOT / ".env"
ENV_TEMPLATE = PROJECT_ROOT / ".env.example"

# Auto-create .env from template if missing
if not ENV_FILE.exists() and ENV_TEMPLATE.exists():
    shutil.copy(str(ENV_TEMPLATE), str(ENV_FILE))
elif not ENV_FILE.exists():
    ENV_FILE.touch()

load_dotenv(dotenv_path=ENV_FILE)

def get_workspace() -> Path:
    """Returns the absolute Path to the workspace directory. Defaults to ~/aether_workspace."""
    default_path = str(Path.home() / "aether_workspace")
    env_path = os.environ.get("AETHER_WORKSPACE", "") or default_path
    p = Path(env_path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    return p

def list_settings() -> dict:
    """Returns all environment variables from the .env file."""
    if not ENV_FILE.exists():
        return {}
    return dotenv_values(ENV_FILE)

def update_setting(key: str, value: str):
    """Updates a single setting in the .env file and reloads it."""
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    set_key(str(ENV_FILE), key, value)
    os.environ[key] = value

def save_all_settings(settings: dict):
    """Batch-save all settings at once, then refresh rotators once."""
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    for key, value in settings.items():
        set_key(str(ENV_FILE), key, str(value))
        os.environ[key] = str(value)
    refresh_all_rotators()

class KeyRotator:
    """Manages round-robin rotation for multiple API keys."""
    def __init__(self, prefix: str, count: int = 4):
        self.prefix = prefix
        self.count = count
        self._refresh()

    def _refresh(self):
        keys = []
        for i in range(1, self.count + 1):
            patterns = [f"{self.prefix}_{i}", f"{self.prefix}{i}"]
            for p in patterns:
                k = os.environ.get(p, "").strip()
                if k:
                    keys.append(k)
                    break
        
        self.valid_keys = [k for k in keys if k]
        self.pool = itertools.cycle(self.valid_keys) if self.valid_keys else None

    def get_key(self) -> str:
        if not self.pool:
            self._refresh()
            if not self.pool:
                single = os.environ.get(self.prefix, "").strip()
                if single: return single
                return None  # Return None instead of crashing
        return next(self.pool)

# Rotators for Free Tier Key Pools - Defined early to avoid NameErrors
GEMINI_ROTATOR = KeyRotator("GEMINI_FREE", 4)
GROQ_ROTATOR = KeyRotator("GROQ_FREE", 4)
OR_ROTATOR = KeyRotator("OR_FREE", 4)

def refresh_all_rotators():
    """Triggers all pre-initialized rotators to reload their key pools from environment."""
    GEMINI_ROTATOR._refresh()
    GROQ_ROTATOR._refresh()
    OR_ROTATOR._refresh()

def get_api_key(service: str) -> str:
    """
    Unified entry point for keys. 
    Respects TIER_MODE (free/paid).
    Returns None if no key is available (instead of crashing).
    """
    mode = os.environ.get("TIER_MODE", "free").lower().strip()
    
    if mode == "paid":
        if service == "brain":
            return os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("CLAUDE_API_KEY", "").strip() or None
        if service == "gemini":
            return os.environ.get("GEMINI_PAID_KEY", "").strip() or None
    
    # Default / Free Tier
    if service == "gemini": return GEMINI_ROTATOR.get_key()
    if service == "groq": return GROQ_ROTATOR.get_key()
    if service == "openrouter": return OR_ROTATOR.get_key()
    if service == "tavily": return os.environ.get("TAVILY_API_KEY", "").strip() or None
    
    return os.environ.get(f"{service.upper()}_API_KEY", "").strip() or None
