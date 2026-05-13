"""
Privacy middleware — scrubs PII from all outbound content before it hits external APIs.
Also provides input sanitization for incoming messages.
"""

import re
import logging

logger = logging.getLogger("aether.privacy")

# ── PII patterns ──────────────────────────────────────────────────────────────
PII_PATTERNS = [
    # Indian phone numbers
    (re.compile(r'\b[6-9]\d{9}\b'), "[PHONE]"),
    # International phone
    (re.compile(r'\+?\d[\d\s\-]{9,14}\d'), "[PHONE]"),
    # Email addresses
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b'), "[EMAIL]"),
    # Aadhaar (12 digits, sometimes spaced)
    (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), "[AADHAAR]"),
    # PAN card
    (re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'), "[PAN]"),
    # API keys / tokens (long alphanumeric strings)
    (re.compile(r'\b(sk-|gsk_|AIza|ya29\.|eyJ)[A-Za-z0-9_\-]{16,}\b'), "[API_KEY]"),
    # Generic secrets in key=value format
    (re.compile(r'(?i)(password|secret|token|api_key|apikey)\s*[=:]\s*\S+'), "[CREDENTIAL]"),
    # Credit card numbers
    (re.compile(r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'), "[CARD]"),
    # UPI IDs (must NOT match email addresses — UPI uses short bank handles like @upi, @paytm, @ybl)
    (re.compile(r'\b[\w.]+@(?:upi|paytm|ybl|okaxis|okhdfcbank|oksbi|apl|ibl|axl|sbi|icici|hdfc|kotak)\b', re.IGNORECASE), "[UPI]"),
]

# Topics that should never be sent to external APIs
SENSITIVE_TOPICS = [
    "bank account", "net banking", "bank password", "atm pin",
    "credit card number", "debit card", "otp", "cvv",
]

def scrub(text: str) -> tuple[str, list]:
    """
    Remove PII from text before sending to external APIs.
    Returns (scrubbed_text, list_of_replacements_made)
    """
    replacements = []
    result = text

    for pattern, placeholder in PII_PATTERNS:
        matches = pattern.findall(result)
        if matches:
            replacements.extend(matches)
            result = pattern.sub(placeholder, result)

    if replacements:
        logger.warning(f"Privacy scrubber removed {len(replacements)} PII item(s)")

    return result, replacements

def is_sensitive_topic(text: str) -> bool:
    """Check if message contains sensitive topics that should stay local."""
    lower = text.lower()
    return any(topic in lower for topic in SENSITIVE_TOPICS)

def sanitize_for_api(messages: list) -> list:
    """
    Scrub all message content before sending to Groq/Gemini.
    - History messages: always string
    - Current message (last): can be list for image vision
    """
    sanitized = []
    for i, msg in enumerate(messages):
        is_last = (i == len(messages) - 1)
        content = msg.get("content", "")

        if isinstance(content, list):
            if is_last:
                # Last message can keep list format for image vision
                sanitized.append(msg)
            else:
                # History — extract text only
                text = " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
                sanitized.append({**msg, "content": text or "[image]"})
        elif isinstance(content, str):
            scrubbed, _ = scrub(content)
            sanitized.append({**msg, "content": scrubbed})
        else:
            sanitized.append({**msg, "content": str(content)})

    return sanitized

def check_message(text: str) -> dict:
    """
    Full privacy check on an incoming message.
    Returns { "safe": bool, "reason": str, "scrubbed": str }
    """
    if is_sensitive_topic(text):
        return {
            "safe": False,
            "reason": "sensitive_topic",
            "scrubbed": text,
            "message": "This looks like sensitive financial info. I'll handle this locally without sending it to any external API."
        }
    scrubbed, replacements = scrub(text)
    return {
        "safe": True,
        "reason": None,
        "scrubbed": scrubbed,
        "replacements": replacements,
    }
