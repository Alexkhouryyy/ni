"""Long-term persistent memory backed by SQLite.

The agent uses two tools:
  - remember(content, kind, importance): store a durable fact/preference/decision
  - recall(query, limit): retrieve relevant past memories

On startup, the top-N most important memories are loaded into the agent's context
so it always knows who you are, what you're working on, and your preferences.
"""
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.path.expanduser("~/.voice_agent_memory.db")


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,           -- fact / preference / project / decision / note
                content TEXT NOT NULL,
                importance INTEGER NOT NULL,  -- 1-10
                tags TEXT DEFAULT ''
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL NOT NULL,
                ended_at REAL,
                summary TEXT DEFAULT ''
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC, ts DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_mem_kind ON memories(kind)")


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def remember(content: str, kind: str = "fact", importance: int = 5, tags: str = "") -> str:
    kind = kind.lower().strip()
    if kind not in {"fact", "preference", "project", "decision", "note"}:
        kind = "note"
    importance = max(1, min(10, int(importance)))
    with _conn() as c:
        c.execute(
            "INSERT INTO memories (ts, kind, content, importance, tags) VALUES (?, ?, ?, ?, ?)",
            (time.time(), kind, content, importance, tags),
        )
        new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return f"Remembered [#{new_id} {kind} importance={importance}]: {content}"


def recall(query: str = "", limit: int = 10, kind: str = "") -> list[dict]:
    """Return memories matching query (LIKE search on content/tags), most important+recent first."""
    sql = "SELECT id, ts, kind, content, importance, tags FROM memories"
    where, params = [], []
    if query:
        where.append("(content LIKE ? OR tags LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if kind:
        where.append("kind = ?")
        params.append(kind.lower())
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY importance DESC, ts DESC LIMIT ?"
    params.append(int(limit))

    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [
        {"id": r[0], "ts": r[1], "kind": r[2], "content": r[3], "importance": r[4], "tags": r[5]}
        for r in rows
    ]


def forget(memory_id: int) -> str:
    with _conn() as c:
        c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    return f"Forgot memory #{memory_id}"


def top_memories(limit: int = 15) -> list[dict]:
    return recall(limit=limit)


def format_for_context(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = ["[Long-term memory — things I know about you and ongoing context:]"]
    for m in memories:
        lines.append(f"  - ({m['kind']}, importance {m['importance']}) {m['content']}")
    return "\n".join(lines)


def start_session() -> int:
    with _conn() as c:
        c.execute("INSERT INTO sessions (started_at) VALUES (?)", (time.time(),))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def end_session(session_id: int, summary: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?",
            (time.time(), summary, session_id),
        )
