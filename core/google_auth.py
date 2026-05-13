"""
Shared Google auth — one service cache for all Google tools.
Prevents rebuilding service on every call.
"""

import logging
from pathlib import Path

logger = logging.getLogger("aether.google_auth")

CREDS_FILE = Path(__file__).parent.parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent.parent / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
]

_creds = None
_services: dict = {}


def get_credentials():
    global _creds
    if _creds and _creds.valid:
        return _creds

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not CREDS_FILE.exists():
                raise FileNotFoundError(f"credentials.json not found at {CREDS_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    _creds = creds
    logger.info("Google credentials loaded/refreshed")
    return creds


def get_service(service_name: str, version: str):
    """Get or create a Google API service client."""
    key = f"{service_name}_{version}"
    if key in _services:
        return _services[key]

    from googleapiclient.discovery import build
    import warnings
    warnings.filterwarnings("ignore", ".*file_cache.*")

    creds = get_credentials()
    service = build(service_name, version, credentials=creds, static_discovery=False)
    _services[key] = service
    logger.info(f"Google service built: {service_name} {version}")
    return service


def invalidate_cache():
    """Call this if auth fails to force re-auth."""
    global _creds, _services
    _creds = None
    _services = {}
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    logger.info("Google auth cache invalidated")
