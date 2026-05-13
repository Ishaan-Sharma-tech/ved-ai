from core.config import get_api_key

def get_gemini_key() -> str:
    """Returns the correct Gemini key based on active tier (Free Rotation or Paid)."""
    return get_api_key("gemini")
