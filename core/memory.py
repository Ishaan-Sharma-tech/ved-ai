import aiosqlite
import json
import time
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "memory", "aether_memory.db")
_db_conn = None

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    task_type TEXT,
    model_used TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""

async def get_db():
    global _db_conn
    if _db_conn is None:
        _db_conn = await aiosqlite.connect(DB_PATH)
        await _db_conn.executescript(CREATE_SQL)
        await _db_conn.commit()
    return _db_conn

async def init_db():
    await get_db()

async def save_turn(session_id: str, role: str, content: str, task_type: str = None, model_used: str = None):
    # Never save list content — always convert to string
    if isinstance(content, list):
        text_parts = []
        for p in content:
            if isinstance(p, dict):
                text_parts.append(p.get("text", ""))
            elif isinstance(p, str):
                text_parts.append(p)
        content = " ".join(text_parts)
        
    db = await get_db()
    await db.execute(
        "INSERT INTO conversations (session_id, role, content, task_type, model_used, timestamp) VALUES (?,?,?,?,?,?)",
        (session_id, role, str(content), task_type, model_used, time.time())
    )
    await db.commit()

async def get_recent(session_id: str, limit: int = 20) -> list[dict]:
    """Get recent turns for THIS session only."""
    db = await get_db()
    async with db.execute(
        "SELECT role, content FROM conversations WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit)
    ) as cur:
        rows = await cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def get_cross_session_context(limit: int = 6) -> list[dict]:
    """
    Get a small slice of recent history across ALL sessions.
    Used only for memory search context — not injected into chat history.
    """
    db = await get_db()
    async with db.execute(
        "SELECT role, content FROM conversations ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ) as cur:
        rows = await cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def search_memory(query: str, limit: int = 5) -> list[dict]:
    """Keyword search across ALL conversations for memory context."""
    words = query.lower().split()[:3]  # Limit words to prevent massive DB sweeps
    if not words:
        return []
        
    db = await get_db()
    results = []
    for word in words:
        async with db.execute(
            "SELECT role, content, timestamp FROM conversations WHERE lower(content) LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{word}%", limit)
        ) as cur:
            rows = await cur.fetchall()
            for r in rows:
                results.append({"role": r[0], "content": r[1], "timestamp": r[2]})
                
    seen = set()
    unique = []
    for r in results:
        key = r["content"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:limit]

async def save_fact(key: str, value: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO facts (key, value, updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
        (key, value, time.time(), value, time.time())
    )
    await db.commit()

async def get_all_facts() -> dict:
    db = await get_db()
    async with db.execute("SELECT key, value FROM facts") as cur:
        rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}
