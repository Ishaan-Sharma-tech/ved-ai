"""
Google Drive tool — list, search, read files.
"""

import asyncio
import logging

TOOL_NAME = "drive"
TOOL_DESCRIPTION = "List, search, read, create, download locally, and upload files in Google Drive"

logger = logging.getLogger("aether.tools.drive")

def _get_service():
    from core.google_auth import get_service
    return get_service("drive", "v3")

from core.config import get_workspace


def _size_str(size: str) -> str:
    try:
        s = int(size)
        if s < 1024: return f"{s}B"
        if s < 1024*1024: return f"{s//1024}KB"
        return f"{s//(1024*1024)}MB"
    except Exception:
        return size


async def run(**kwargs) -> str:
    action = kwargs.get("action", "").lower().strip()
    query = kwargs.get("query") or kwargs.get("search") or ""
    file_id = kwargs.get("file_id") or kwargs.get("id") or ""
    
    try:
        count = int(kwargs.get("count", 10))
    except (ValueError, TypeError):
        count = 10
        
    name = kwargs.get("name") or kwargs.get("filename") or kwargs.get("file") or kwargs.get("path") or ""
    content = kwargs.get("content") or kwargs.get("text") or kwargs.get("body") or ""

    try:
        service = await asyncio.to_thread(_get_service)
    except Exception as e:
        return f"Drive connect nahi hua: {e}"

    # ── List recent files ──────────────────────────────────────────────────────
    if action == "list":
        try:
            result = await asyncio.to_thread(lambda: service.files().list(
                pageSize=int(count),
                fields="files(id,name,mimeType,size,modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute())
            files = result.get("files", [])
            if not files:
                return "Drive mein koi file nahi mili."
            lines = []
            for i, f in enumerate(files, 1):
                name = f.get("name", "Unknown")
                size = _size_str(f.get("size", "0"))
                mime = f.get("mimeType", "").split(".")[-1]
                lines.append(f"{i}. {name} ({size}) [{mime}]")
            return f"Recent Drive files:\n" + "\n".join(lines)
        except Exception as e:
            return f"Drive list nahi hua: {e}"

    # ── Search files ───────────────────────────────────────────────────────────
    elif action == "search":
        if not query:
            return "Search query bata yaar."
        try:
            result = await asyncio.to_thread(lambda: service.files().list(
                q=f"name contains '{query}'",
                pageSize=10,
                fields="files(id,name,mimeType,size,modifiedTime)"
            ).execute())
            files = result.get("files", [])
            if not files:
                return f"'{query}' naam ki koi file nahi mili Drive mein."
            lines = []
            for i, f in enumerate(files, 1):
                name = f.get("name", "Unknown")
                size = _size_str(f.get("size", "0"))
                fid = f.get("id", "")
                lines.append(f"{i}. {name} ({size})\n   ID: {fid}")
            return f"Search results for '{query}':\n\n" + "\n\n".join(lines)
        except Exception as e:
            return f"Drive search nahi hua: {e}"

    # ── Read file content ──────────────────────────────────────────────────────
    elif action == "read":
        if not file_id:
            return "file_id bata (search se milega)."
        try:
            # Get file metadata first
            meta = await asyncio.to_thread(lambda: service.files().get(
                fileId=file_id, fields="name,mimeType"
            ).execute())
            name = meta.get("name", "file")
            mime = meta.get("mimeType", "")

            # Export Google Docs as plain text
            if "google-apps.document" in mime:
                content = await asyncio.to_thread(lambda: service.files().export(
                    fileId=file_id, mimeType="text/plain"
                ).execute())
                text = content.decode("utf-8", errors="replace")[:3000]
                return f"--- {name} ---\n{text}"
            else:
                # Download raw file
                content = await asyncio.to_thread(lambda: service.files().get_media(
                    fileId=file_id
                ).execute())
                try:
                    text = content.decode("utf-8", errors="replace")[:3000]
                    return f"--- {name} ---\n{text}"
                except Exception:
                    return f"'{name}' binary file hai — read nahi ho sakta directly."
        except Exception as e:
            return f"File read nahi hua: {e}"

    # ── Storage info ───────────────────────────────────────────────────────────
    elif action == "storage":
        try:
            result = await asyncio.to_thread(lambda: service.about().get(
                fields="storageQuota"
            ).execute())
            quota = result.get("storageQuota", {})
            used = int(quota.get("usage", 0)) // (1024*1024)
            total = int(quota.get("limit", 0)) // (1024*1024)
            return f"Drive storage: {used}MB used of {total}MB"
        except Exception as e:
            return f"Storage info nahi mila: {e}"

    # ── Create file ────────────────────────────────────────────────────────────
    elif action == "create":
        if not name or not content:
            return "File ka naam aur content dono chahiye."
        try:
            from googleapiclient.http import MediaIoBaseUpload
            import io
            file_metadata = {'name': name}
            media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype='text/plain', resumable=False)
            result = await asyncio.to_thread(lambda: service.files().create(
                body=file_metadata, media_body=media, fields='id'
            ).execute())
            return f"Drive mein file create ho gayi: {name} (ID: {result.get('id')})"
        except Exception as e:
            return f"Drive mein file create nahi hui: {e}"

    # ── Advanced 2-Way Sync ────────────────────────────────────────────────────
    elif action == "download":
        if not file_id:
            return "download ke liye file_id zaruri hai."
        try:
            import os
            save_dir = get_workspace()
            save_dir.mkdir(parents=True, exist_ok=True)
            meta = await asyncio.to_thread(lambda: service.files().get(
                fileId=file_id, fields="name,mimeType"
            ).execute())
            name = meta.get("name", "downloaded_file")
            content = await asyncio.to_thread(lambda: service.files().get_media(
                fileId=file_id
            ).execute())
            path = save_dir / name
            with open(path, "wb") as f:
                f.write(content)
            return f"File successfully downloaded to sandbox: {path}"
        except Exception as e:
            return f"Download fail: {e}"

    elif action == "upload":
        if not name:
            ws = get_workspace()
            return f"upload ke liye file ka absolute path 'name' field me do (e.g., {ws / 'stats.csv'})"
        try:
            import os
            from googleapiclient.http import MediaFileUpload
            if not os.path.exists(name):
                return f"Local file not found: {name}"
            filename = os.path.basename(name)
            file_metadata = {'name': filename}
            media = MediaFileUpload(name, resumable=False)
            result = await asyncio.to_thread(lambda: service.files().create(
                body=file_metadata, media_body=media, fields='id'
            ).execute())
            return f"File successfully uploaded to Drive: {filename} (ID: {result.get('id')})"
        except Exception as e:
            return f"Upload fail: {e}"

    else:
        return "Available actions: list, search, read, storage, create, download, upload"
