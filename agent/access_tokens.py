"""Per-device access tokens — revocable credentials for the dashboard.

Today Apex authenticates every request against a single shared DASHBOARD_TOKEN.
That works, but to cut off one lost phone you must rotate the secret on EVERY
device. This module adds per-device tokens you can revoke individually:

  - issue(label) mints a fresh token, shown ONCE, and stores only its SHA-256
    hash (a DB leak never exposes a live token).
  - verify(token) accepts any non-revoked device token (and refreshes last_used).
  - revoke(id) cuts off exactly one device; the master token and all others keep
    working.

The shared DASHBOARD_TOKEN remains the "master" credential (and the only one that
may mint/revoke device tokens — enforced in the dashboard layer).
"""
from __future__ import annotations

import hashlib
import secrets
import time

from agent import longterm

_PREFIX = "apxd_"


def init_db() -> None:
    with longterm._conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS access_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT UNIQUE NOT NULL,
                label      TEXT DEFAULT '',
                device_id  TEXT DEFAULT '',
                created_at REAL NOT NULL,
                last_used  REAL,
                revoked    INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_access_tokens_hash ON access_tokens(token_hash)")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(label: str = "", device_id: str = "") -> str:
    """Mint a new device token. Returns the RAW token (store it now — it is never
    recoverable; only its hash is persisted)."""
    token = _PREFIX + secrets.token_urlsafe(32)
    with longterm._conn() as c:
        c.execute(
            "INSERT INTO access_tokens (token_hash, label, device_id, created_at, last_used, revoked) "
            "VALUES (?, ?, ?, ?, NULL, 0)",
            (_hash(token), label or "", device_id or "", time.time()),
        )
    return token


def verify(token: str | None) -> bool:
    """True if `token` is a known, non-revoked device token. Refreshes last_used."""
    if not token or not token.startswith(_PREFIX):
        return False
    th = _hash(token)
    with longterm._conn() as c:
        row = c.execute(
            "SELECT id FROM access_tokens WHERE token_hash = ? AND revoked = 0",
            (th,),
        ).fetchone()
        if not row:
            return False
        c.execute("UPDATE access_tokens SET last_used = ? WHERE id = ?", (time.time(), row[0]))
    return True


def list_tokens() -> list[dict]:
    """All device tokens (metadata only — never the hash or raw token)."""
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id, label, device_id, created_at, last_used, revoked "
            "FROM access_tokens ORDER BY created_at DESC"
        ).fetchall()
    return [
        {"id": r[0], "label": r[1], "device_id": r[2], "created_at": r[3],
         "last_used": r[4], "revoked": bool(r[5])}
        for r in rows
    ]


def revoke(token_id: int) -> bool:
    with longterm._conn() as c:
        cur = c.execute("UPDATE access_tokens SET revoked = 1 WHERE id = ?", (int(token_id),))
        return cur.rowcount > 0


def revoke_all() -> int:
    with longterm._conn() as c:
        cur = c.execute("UPDATE access_tokens SET revoked = 1 WHERE revoked = 0")
        return cur.rowcount
