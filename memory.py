"""
JARVIS Memory & Planning — persistent context, tasks, notes, and smart routing.

Three systems:
1. Memory — facts, preferences, project context JARVIS learns from conversations
2. Tasks — to-do items with priority, due dates, project association
3. Notes — freeform context tied to projects, people, or topics

Everything stored in SQLite. Relevant memories injected into every LLM call
so JARVIS gets smarter over time.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("jarvis.memory")

DB_PATH = Path(__file__).parent / "data" / "jarvis.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,          -- 'fact', 'preference', 'project', 'person', 'decision'
            content TEXT NOT NULL,
            source TEXT DEFAULT '',      -- what conversation/context it came from
            importance INTEGER DEFAULT 5, -- 1-10, higher = more important
            created_at REAL NOT NULL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium', -- 'high', 'medium', 'low'
            status TEXT DEFAULT 'open',     -- 'open', 'in_progress', 'done', 'cancelled'
            due_date TEXT,                  -- ISO date string
            due_time TEXT,                  -- HH:MM
            project TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',         -- JSON array
            notes TEXT DEFAULT '',
            created_at REAL NOT NULL,
            completed_at REAL
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            topic TEXT DEFAULT '',       -- project name, person, or topic
            tags TEXT DEFAULT '[]',      -- JSON array
            created_at REAL NOT NULL,
            updated_at REAL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, type, source,
            content='memories', content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS task_fts USING fts5(
            title, description, project, notes,
            content='tasks', content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(
            title, content, topic,
            content='notes', content_rowid='id'
        );

        CREATE TABLE IF NOT EXISTS saved_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL UNIQUE,
            full_address TEXT NOT NULL,
            phone TEXT,
            region TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            provider_order_id TEXT,
            restaurant TEXT NOT NULL,
            items_json TEXT NOT NULL,
            subtotal REAL,
            fees REAL,
            total REAL,
            currency TEXT DEFAULT 'USD',
            address_id INTEGER REFERENCES saved_addresses(id),
            payment_method TEXT NOT NULL DEFAULT 'cash_on_delivery',
            status TEXT NOT NULL,
            eta_minutes INTEGER,
            aborted_reason TEXT,
            created_at REAL NOT NULL,
            updated_at REAL
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            restaurant TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            party_size INTEGER NOT NULL,
            reservation_time TEXT NOT NULL,
            drafted_message TEXT,
            status TEXT NOT NULL,
            created_at REAL NOT NULL
        );
    """)
    conn.close()
    log.info("Memory database initialized")


# ---------------------------------------------------------------------------
# Memories — facts JARVIS learns
# ---------------------------------------------------------------------------

def remember(content: str, mem_type: str = "fact", source: str = "", importance: int = 5) -> int:
    """Store a memory. Returns the memory ID."""
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO memories (type, content, source, importance, created_at) VALUES (?, ?, ?, ?, ?)",
        (mem_type, content, source, importance, time.time())
    )
    mem_id = cur.lastrowid
    # Update FTS
    conn.execute(
        "INSERT INTO memory_fts (rowid, content, type, source) VALUES (?, ?, ?, ?)",
        (mem_id, content, mem_type, source)
    )
    conn.commit()
    conn.close()
    log.info(f"Stored memory [{mem_type}]: {content[:60]}")
    return mem_id


def _sanitize_fts_query(query: str) -> str:
    """Clean a query string for FTS5 — remove special characters that break it."""
    # Remove apostrophes, quotes, and FTS operators
    cleaned = query.replace("'", "").replace('"', "").replace("*", "").replace("-", " ")
    # Take meaningful words only
    words = [w for w in cleaned.split() if len(w) > 2]
    if not words:
        return ""
    # Join with OR for broader matching
    return " OR ".join(words[:5])


def recall(query: str, limit: int = 5) -> list[dict]:
    """Search memories by relevance. Returns most relevant matches."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT m.id, m.type, m.content, m.importance, m.created_at, m.access_count
            FROM memory_fts f
            JOIN memories m ON f.rowid = m.id
            WHERE memory_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []

    # Update access counts
    for r in results:
        conn.execute(
            "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
            (time.time(), r["id"])
        )
    conn.commit()
    conn.close()
    return [dict(r) for r in results]


def get_recent_memories(limit: int = 10) -> list[dict]:
    """Get most recent memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_important_memories(limit: int = 10) -> list[dict]:
    """Get highest importance memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories ORDER BY importance DESC, access_count DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def forget(query: str) -> int:
    """Delete memories matching a query. Returns number of rows removed.

    Uses FTS5 to find matching memories, then deletes them from both tables.
    Pass an empty string or "*" to wipe everything (use sparingly).
    """
    conn = _get_db()
    try:
        if not query or query.strip() in ("*", "all", "everything"):
            # Nuke all memories
            n = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            conn.executescript(
                "DELETE FROM memories; DELETE FROM memory_fts;"
            )
            conn.commit()
            log.info(f"Forgot all {n} memories")
            return n
        # Find matching rows via FTS
        fts_q = _sanitize_fts_query(query)
        if not fts_q:
            return 0
        rows = conn.execute(
            "SELECT m.id FROM memory_fts f JOIN memories m ON f.rowid = m.id "
            "WHERE memory_fts MATCH ?",
            (fts_q,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM memory_fts WHERE rowid IN ({placeholders})", ids)
        conn.commit()
        log.info(f"Forgot {len(ids)} memories matching '{query}'")
        return len(ids)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(title: str, description: str = "", priority: str = "medium",
                due_date: str = "", due_time: str = "", project: str = "",
                tags: list[str] = None) -> int:
    """Create a task. Returns task ID."""
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO tasks (title, description, priority, due_date, due_time,
           project, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, priority, due_date, due_time,
         project, json.dumps(tags or []), time.time())
    )
    task_id = cur.lastrowid
    conn.execute(
        "INSERT INTO task_fts (rowid, title, description, project, notes) VALUES (?, ?, ?, ?, ?)",
        (task_id, title, description, project, "")
    )
    conn.commit()
    conn.close()
    log.info(f"Created task [{priority}]: {title}")
    return task_id


def get_open_tasks(project: str = None) -> list[dict]:
    """Get all open/in-progress tasks, optionally filtered by project."""
    conn = _get_db()
    if project:
        results = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('open','in_progress') AND project LIKE ? ORDER BY "
            "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date",
            (f"%{project}%",)
        ).fetchall()
    else:
        results = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('open','in_progress') ORDER BY "
            "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date"
        ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_tasks_for_date(date_str: str) -> list[dict]:
    """Get tasks due on a specific date (YYYY-MM-DD)."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM tasks WHERE due_date = ? AND status != 'cancelled' ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_time",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def complete_task(task_id: int):
    """Mark a task as done."""
    conn = _get_db()
    conn.execute(
        "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
        (time.time(), task_id)
    )
    conn.commit()
    conn.close()


def search_tasks(query: str, limit: int = 10) -> list[dict]:
    """Search tasks by text."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT t.* FROM task_fts f
            JOIN tasks t ON f.rowid = t.id
            WHERE task_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def create_note(content: str, title: str = "", topic: str = "", tags: list[str] = None) -> int:
    """Create a note. Returns note ID."""
    conn = _get_db()
    now = time.time()
    cur = conn.execute(
        "INSERT INTO notes (title, content, topic, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, content, topic, json.dumps(tags or []), now, now)
    )
    note_id = cur.lastrowid
    conn.execute(
        "INSERT INTO note_fts (rowid, title, content, topic) VALUES (?, ?, ?, ?)",
        (note_id, title, content, topic)
    )
    conn.commit()
    conn.close()
    log.info(f"Created note: {title or content[:40]}")
    return note_id


def search_notes(query: str, limit: int = 10) -> list[dict]:
    """Search notes by text."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT n.* FROM note_fts f
            JOIN notes n ON f.rowid = n.id
            WHERE note_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []
    conn.close()
    return [dict(r) for r in results]


def get_notes_by_topic(topic: str) -> list[dict]:
    """Get all notes for a topic/project."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM notes WHERE topic LIKE ? ORDER BY updated_at DESC",
        (f"%{topic}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Context Builder — smart context for LLM calls
# ---------------------------------------------------------------------------

def build_memory_context(user_message: str) -> str:
    """Build relevant context from memories, tasks, and notes for the LLM.

    Searches for relevant memories based on what the user is talking about.
    Fast — runs FTS queries, no heavy computation.
    """
    parts = []

    # Always include: open high-priority tasks
    high_tasks = [t for t in get_open_tasks() if t["priority"] == "high"]
    if high_tasks:
        task_lines = [f"  - [{t['priority']}] {t['title']}" +
                      (f" (due {t['due_date']})" if t["due_date"] else "")
                      for t in high_tasks[:5]]
        parts.append("HIGH PRIORITY TASKS:\n" + "\n".join(task_lines))

    # Search memories relevant to what user is saying
    if len(user_message) > 5:
        relevant = recall(user_message, limit=3)
        if relevant:
            mem_lines = [f"  - [{m['type']}] {m['content']}" for m in relevant]
            parts.append("RELEVANT MEMORIES:\n" + "\n".join(mem_lines))

    # Recent important memories (always available)
    important = get_important_memories(limit=3)
    if important:
        imp_lines = [f"  - {m['content']}" for m in important
                     if not any(m["content"] == r["content"] for r in (relevant if 'relevant' in dir() else []))]
        if imp_lines:
            parts.append("KEY FACTS:\n" + "\n".join(imp_lines[:3]))

    return "\n\n".join(parts) if parts else ""


def format_tasks_for_voice(tasks: list[dict]) -> str:
    """Format tasks for voice response."""
    if not tasks:
        return "No tasks on the list, sir."
    count = len(tasks)
    high = [t for t in tasks if t["priority"] == "high"]
    if count == 1:
        t = tasks[0]
        return f"One task: {t['title']}." + (f" Due {t['due_date']}." if t["due_date"] else "")
    result = f"You have {count} open tasks."
    if high:
        result += f" {len(high)} are high priority."
    top = tasks[:3]
    for t in top:
        result += f" {t['title']}."
    if count > 3:
        result += f" And {count - 3} more."
    return result


def format_plan_for_voice(tasks: list[dict], events: list[dict]) -> str:
    """Format a day plan combining tasks and calendar events."""
    if not tasks and not events:
        return "Your day looks clear, sir. No events or tasks scheduled."

    parts = []
    if events:
        parts.append(f"{len(events)} events on the calendar")
    if tasks:
        high = [t for t in tasks if t["priority"] == "high"]
        parts.append(f"{len(tasks)} tasks" + (f", {len(high)} high priority" if high else ""))

    result = f"For tomorrow: {', '.join(parts)}. "

    # List events first
    if events:
        for e in events[:3]:
            result += f"{e.get('start', '')} {e['title']}. "

    # Then high priority tasks
    if tasks:
        for t in [t for t in tasks if t["priority"] == "high"][:2]:
            result += f"Priority: {t['title']}. "

    result += "Shall I adjust anything?"
    return result


# ---------------------------------------------------------------------------
# Memory extraction — learn from conversations
# ---------------------------------------------------------------------------

async def extract_memories(user_text: str, jarvis_response: str, anthropic_client) -> list[str]:
    """After a conversation turn, extract any facts worth remembering.

    Uses Haiku to decide if anything in the exchange is worth storing.
    Returns list of memories stored.
    """
    if not anthropic_client or len(user_text) < 15:
        return []

    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "Extract facts worth remembering from this conversation. "
                "Only extract CONCRETE facts: preferences, decisions, names, dates, plans, goals. "
                "NOT opinions, greetings, or casual chat. "
                "Return JSON array of objects: [{\"type\": \"fact|preference|project|person|decision\", \"content\": \"...\", \"importance\": 1-10}] "
                "Return [] if nothing worth remembering. Be very selective."
            ),
            messages=[{"role": "user", "content": f"User: {user_text}\nJARVIS: {jarvis_response}"}],
        )

        text = response.content[0].text.strip()
        # Parse JSON
        if text.startswith("["):
            items = json.loads(text)
            stored = []
            for item in items:
                if isinstance(item, dict) and "content" in item:
                    remember(
                        content=item["content"],
                        mem_type=item.get("type", "fact"),
                        source=user_text[:50],
                        importance=item.get("importance", 5),
                    )
                    stored.append(item["content"])
            return stored
    except Exception as e:
        log.debug(f"Memory extraction failed: {e}")

    return []


# ---------------------------------------------------------------------------
# Saved Addresses
# ---------------------------------------------------------------------------

def save_address(label: str, full_address: str, region: str,
                 phone: str = "", is_default: bool = False) -> int:
    """Save or update a delivery address. Returns address ID."""
    conn = _get_db()
    # Upsert by label (UNIQUE constraint)
    conn.execute(
        """INSERT INTO saved_addresses (label, full_address, phone, region, is_default, created_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(label) DO UPDATE SET
               full_address=excluded.full_address,
               phone=excluded.phone,
               region=excluded.region,
               is_default=excluded.is_default""",
        (label.lower(), full_address, phone, region, int(is_default), time.time())
    )
    addr_id = conn.execute(
        "SELECT id FROM saved_addresses WHERE label = ?", (label.lower(),)
    ).fetchone()["id"]
    conn.commit()
    conn.close()
    log.info(f"Saved address [{label}]: {full_address[:50]}")
    return addr_id


def get_address(label: str) -> dict | None:
    """Get a saved address by label ('home', 'office', etc.). Returns None if not found."""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM saved_addresses WHERE label = ?", (label.lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_default_address() -> dict | None:
    """Get the default delivery address."""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM saved_addresses WHERE is_default = 1 LIMIT 1"
    ).fetchone()
    if not row:
        # Fall back to first saved address
        row = conn.execute(
            "SELECT * FROM saved_addresses ORDER BY created_at LIMIT 1"
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_addresses() -> list[dict]:
    """List all saved addresses."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM saved_addresses ORDER BY is_default DESC, created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def record_order(provider: str, restaurant: str, items_json: str,
                 address_id: int = None, currency: str = "USD",
                 subtotal: float = None, fees: float = None,
                 total: float = None) -> int:
    """Insert a new order row with status='pending_confirm'. Returns order ID."""
    now = time.time()
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO orders
           (provider, restaurant, items_json, address_id, currency,
            subtotal, fees, total, status, payment_method, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_confirm', 'cash_on_delivery', ?, ?)""",
        (provider, restaurant, items_json, address_id, currency,
         subtotal, fees, total, now, now)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    log.info(f"Recorded order #{order_id}: {restaurant} via {provider}")
    return order_id


def update_order_status(order_id: int, status: str,
                        provider_order_id: str = None,
                        eta_minutes: int = None,
                        aborted_reason: str = None,
                        subtotal: float = None,
                        fees: float = None,
                        total: float = None):
    """Update an order's status and optional fields."""
    conn = _get_db()
    fields = ["status = ?", "updated_at = ?"]
    values = [status, time.time()]
    if provider_order_id is not None:
        fields.append("provider_order_id = ?")
        values.append(provider_order_id)
    if eta_minutes is not None:
        fields.append("eta_minutes = ?")
        values.append(eta_minutes)
    if aborted_reason is not None:
        fields.append("aborted_reason = ?")
        values.append(aborted_reason)
    if subtotal is not None:
        fields.append("subtotal = ?")
        values.append(subtotal)
    if fees is not None:
        fields.append("fees = ?")
        values.append(fees)
    if total is not None:
        fields.append("total = ?")
        values.append(total)
    values.append(order_id)
    conn.execute(f"UPDATE orders SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    log.info(f"Order #{order_id} → {status}")


def get_order(order_id: int) -> dict | None:
    """Fetch a single order by ID."""
    conn = _get_db()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def recent_orders(limit: int = 10) -> list[dict]:
    """Get recent orders sorted newest-first."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_order(provider: str = None) -> dict | None:
    """Get the currently in-flight order (pending_confirm or submitted).
    Optionally filtered by provider.
    """
    conn = _get_db()
    if provider:
        row = conn.execute(
            """SELECT * FROM orders WHERE status IN ('pending_confirm','submitted')
               AND provider = ? ORDER BY created_at DESC LIMIT 1""",
            (provider,)
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT * FROM orders WHERE status IN ('pending_confirm','submitted')
               ORDER BY created_at DESC LIMIT 1"""
        ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Reservations
# ---------------------------------------------------------------------------

def record_reservation(provider: str, restaurant: str, party_size: int,
                        reservation_time: str, phone: str = "",
                        email: str = "", drafted_message: str = "") -> int:
    """Insert a reservation row with status='draft'. Returns reservation ID."""
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO reservations
           (provider, restaurant, phone, email, party_size, reservation_time,
            drafted_message, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)""",
        (provider, restaurant, phone, email, party_size,
         reservation_time, drafted_message, time.time())
    )
    res_id = cur.lastrowid
    conn.commit()
    conn.close()
    log.info(f"Recorded reservation #{res_id}: {restaurant} for {party_size} at {reservation_time}")
    return res_id


def update_reservation_status(reservation_id: int, status: str):
    """Update a reservation's status (draft → sent → confirmed / declined)."""
    conn = _get_db()
    conn.execute(
        "UPDATE reservations SET status = ? WHERE id = ?", (status, reservation_id)
    )
    conn.commit()
    conn.close()


def recent_reservations(limit: int = 10) -> list[dict]:
    """Get recent reservations newest-first."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM reservations ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
init_db()
