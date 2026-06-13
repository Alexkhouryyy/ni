"""Device registry — track which devices are connected to this Apex.

Every client (desktop browser, mobile PWA, extension) carries a persistent
device id and announces itself over the live WebSocket. We record a heartbeat so
the dashboard can show what's connected and so the Notification Hub can route
"normal" nudges to the device you're actually using, while still fanning urgent
(high-priority) alerts out to everything.

Storage shares the longterm SQLite DB.
"""
from __future__ import annotations

import time

from agent import longterm


def init_db() -> None:
    """Create the devices table if absent. Idempotent."""
    with longterm._conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                device_id  TEXT PRIMARY KEY,
                label      TEXT DEFAULT '',
                kind       TEXT DEFAULT 'web',
                user_agent TEXT DEFAULT '',
                created_at REAL NOT NULL,
                last_seen  REAL NOT NULL
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_devices_seen ON devices(last_seen DESC)")


def touch(device_id: str, *, label: str = "", kind: str = "web", user_agent: str = "") -> None:
    """Upsert a device and refresh its heartbeat. No-op on empty id."""
    if not device_id:
        return
    now = time.time()
    with longterm._conn() as c:
        c.execute(
            """
            INSERT INTO devices (device_id, label, kind, user_agent, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                last_seen=excluded.last_seen,
                label=CASE WHEN excluded.label != '' THEN excluded.label ELSE devices.label END,
                kind=CASE WHEN excluded.kind != '' THEN excluded.kind ELSE devices.kind END,
                user_agent=CASE WHEN excluded.user_agent != '' THEN excluded.user_agent ELSE devices.user_agent END
            """,
            (device_id, label, kind, user_agent, now, now),
        )


def list_devices(fresh_seconds: int = 300) -> list[dict]:
    """All known devices, newest heartbeat first, with an `online` flag."""
    now = time.time()
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT device_id, label, kind, user_agent, created_at, last_seen "
            "FROM devices ORDER BY last_seen DESC"
        ).fetchall()
    return [
        {
            "device_id": r[0], "label": r[1], "kind": r[2], "user_agent": r[3],
            "created_at": r[4], "last_seen": r[5],
            "online": (now - r[5]) <= fresh_seconds,
        }
        for r in rows
    ]


def active_device_id(fresh_seconds: int = 300) -> str | None:
    """The most recently active device, if any has a heartbeat within the window."""
    cutoff = time.time() - fresh_seconds
    with longterm._conn() as c:
        row = c.execute(
            "SELECT device_id FROM devices WHERE last_seen >= ? "
            "ORDER BY last_seen DESC LIMIT 1",
            (cutoff,),
        ).fetchone()
    return row[0] if row else None


def forget(device_id: str) -> None:
    with longterm._conn() as c:
        c.execute("DELETE FROM devices WHERE device_id=?", (device_id,))
