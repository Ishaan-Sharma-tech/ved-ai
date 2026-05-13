"""
Gmail tool — read inbox, send emails, search mail.
"""

import asyncio
import logging
import base64
from email.message import EmailMessage

TOOL_NAME = "gmail"
TOOL_DESCRIPTION = "Read inbox, send/draft emails, read full threads, search — full email management"

logger = logging.getLogger("aether.tools.gmail")


def _get_service():
    from core.google_auth import get_service
    return get_service("gmail", "v1")


def _decode_body(payload) -> str:
    """Extract email body text."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return body[:500] if body else "(no body)"


async def run(**kwargs) -> str:
    action = kwargs.get("action", "").lower().strip()
    query = kwargs.get("query") or kwargs.get("search") or ""
    to = kwargs.get("to") or kwargs.get("recipient") or ""
    subject = kwargs.get("subject") or kwargs.get("title") or ""
    body = kwargs.get("body") or kwargs.get("content") or kwargs.get("text") or ""
    
    try:
        count = int(kwargs.get("count", 5))
    except (ValueError, TypeError):
        count = 5
        
    message_id = kwargs.get("message_id") or kwargs.get("id") or ""

    try:
        service = await asyncio.to_thread(_get_service)
    except Exception as e:
        return f"Gmail connect nahi hua: {e}"

    # ── Read inbox ─────────────────────────────────────────────────────────────
    if action == "inbox":
        try:
            result = await asyncio.to_thread(lambda: service.users().messages().list(
                userId="me", labelIds=["INBOX"], maxResults=int(count)
            ).execute())
            messages = result.get("messages", [])
            if not messages:
                return "Inbox empty hai yaar!"
            lines = []
            for i, msg in enumerate(messages, 1):
                detail = await asyncio.to_thread(lambda m=msg: service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute())
                headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                sender = headers.get("From", "Unknown")[:40]
                subj = headers.get("Subject", "No subject")[:50]
                lines.append(f"{i}. From: {sender}\n   Subject: {subj}")
            return f"Inbox ({count} emails):\n\n" + "\n\n".join(lines)
        except Exception as e:
            return f"Inbox fetch nahi hua: {e}"

    # ── Search ─────────────────────────────────────────────────────────────────
    elif action == "search":
        if not query:
            return "Search query bata yaar."
        try:
            result = await asyncio.to_thread(lambda: service.users().messages().list(
                userId="me", q=query, maxResults=5
            ).execute())
            messages = result.get("messages", [])
            if not messages:
                return f"Koi email nahi mila '{query}' ke liye."
            lines = []
            for i, msg in enumerate(messages, 1):
                detail = await asyncio.to_thread(lambda m=msg: service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute())
                headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                sender = headers.get("From", "Unknown")[:40]
                subj = headers.get("Subject", "No subject")[:50]
                lines.append(f"{i}. From: {sender}\n   Subject: {subj}")
            return f"Search results for '{query}':\n\n" + "\n\n".join(lines)
        except Exception as e:
            return f"Search nahi hua: {e}"

    # ── Read specific email ────────────────────────────────────────────────────
    elif action == "read":
        if not message_id:
            return "message_id bata."
        try:
            detail = await asyncio.to_thread(lambda: service.users().messages().get(
                userId="me", id=message_id, format="full"
            ).execute())
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            sender = headers.get("From", "Unknown")
            subj = headers.get("Subject", "No subject")
            body_text = _decode_body(detail["payload"])
            return f"From: {sender}\nSubject: {subj}\n\n{body_text}"
        except Exception as e:
            return f"Email read nahi hua: {e}"

    # ── Send email ─────────────────────────────────────────────────────────────
    elif action == "send":
        if not to or not subject or not body:
            return "to, subject aur body sab chahiye bhai."
        try:
            profile = await asyncio.to_thread(lambda: service.users().getProfile(userId="me").execute())
            my_email = profile.get("emailAddress", "me")
            
            msg = EmailMessage()
            msg.set_content(body)
            msg["To"] = to
            msg["From"] = my_email
            msg["Subject"] = subject
            
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            await asyncio.to_thread(lambda: service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute())
            return f"Email send ho gaya yaar! To: {to}, Subject: {subject}"
        except Exception as e:
            return f"Email send nahi hua: {e}"

    # ── Unread count ───────────────────────────────────────────────────────────
    elif action == "unread":
        try:
            result = await asyncio.to_thread(lambda: service.users().messages().list(
                userId="me", labelIds=["UNREAD", "INBOX"], maxResults=int(count)
            ).execute())
            messages = result.get("messages", [])
            total_est = result.get("resultSizeEstimate", 0)
            if not messages:
                return "Koi unread emails nahi hain yaar!"
                
            lines = []
            for i, msg in enumerate(messages, 1):
                detail = await asyncio.to_thread(lambda m=msg: service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute())
                headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                sender = headers.get("From", "Unknown")[:40]
                subj = headers.get("Subject", "No subject")[:50]
                lines.append(f"{i}. From: {sender}\n   Subject: {subj}")
                
            return f"You have approximately {total_est} unread emails. Here are the top {len(messages)} unread:\n\n" + "\n\n".join(lines)
        except Exception as e:
            return f"Unread count nahi mila: {e}"

    # ── Advanced Features ──────────────────────────────────────────────────────
    elif action == "draft":
        if not to or not subject or not body:
            return "to, subject aur body sab chahiye draft ke liye."
        try:
            profile = await asyncio.to_thread(lambda: service.users().getProfile(userId="me").execute())
            my_email = profile.get("emailAddress", "me")
            
            msg = EmailMessage()
            msg.set_content(body)
            msg["To"] = to
            msg["From"] = my_email
            msg["Subject"] = subject
            
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            await asyncio.to_thread(lambda: service.users().drafts().create(
                userId="me", body={"message": {"raw": raw}}
            ).execute())
            return f"Draft saved perfectly in your Gmail account for '{subject}'. You can review and sent it from your phone!"
        except Exception as e:
            return f"Draft save nahi hua: {e}"

    elif action == "read_thread":
        if not message_id:
            return "Thread ID (message_id) required."
        try:
            # message_id works as threadId usually if it's the root message
            detail = await asyncio.to_thread(lambda: service.users().threads().get(
                userId="me", id=message_id, format="full"
            ).execute())
            messages = detail.get("messages", [])
            output = [f"--- Thread contains {len(messages)} messages ---"]
            for msg in messages:
                headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
                sender = headers.get("From", "Unknown")
                date = headers.get("Date", "")
                body_text = _decode_body(msg["payload"])
                output.append(f"From: {sender} ({date})\n{body_text}\n---")
            return "\n".join(output)[:4000] # Cap output limit
        except Exception as e:
            return f"Thread read fail: {e}"

    else:
        return "Available actions: inbox, search, read, send, unread, draft, read_thread"
