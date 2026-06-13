"""Notification Hub — fan one proactive message out to every device.

Apex's proactive producers (Guardian Angel, Time Capsule, briefings, scheduled
tasks) used to reach the user only through the host machine's tray + TTS. This hub
turns a single `notify(...)` call into delivery across every surface:

  • WebSocket  → in-app toast on any open dashboard/PWA client
  • Web Push   → native OS notification on subscribed devices, even when closed
  • Telegram   → zero-infra fallback so the user is still reachable before any
                 push subscription exists

Voice (local TTS) and the desktop tray remain owned by the individual producers —
this hub is specifically the *cross-device* reach layer. Calls are deduped so the
same event firing from multiple threads/sinks only notifies once.

Web Push uses VAPID; subscriptions live in the shared longterm SQLite DB. If
`pywebpush` is not installed the push sink degrades to a no-op (the other sinks
still work), so the hub never hard-fails.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Callable, Optional

import config
from agent import longterm


# ── Subscription storage (shared longterm DB) ────────────────────────────────

def init_push_table() -> None:
    """Create the push_subscriptions table if absent. Idempotent."""
    with longterm._conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                device_label TEXT DEFAULT '',
                created_at REAL NOT NULL,
                last_seen REAL NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_push_endpoint "
            "ON push_subscriptions(endpoint)"
        )


def add_subscription(sub: dict, device_label: str = "") -> int:
    """Insert or refresh a Web Push subscription. Returns its row id."""
    endpoint = sub.get("endpoint", "")
    keys = sub.get("keys", {}) or {}
    p256dh = keys.get("p256dh", "")
    auth = keys.get("auth", "")
    if not (endpoint and p256dh and auth):
        raise ValueError("subscription missing endpoint/keys")
    now = time.time()
    with longterm._conn() as c:
        c.execute(
            """
            INSERT INTO push_subscriptions (endpoint, p256dh, auth, device_label, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                p256dh=excluded.p256dh, auth=excluded.auth,
                device_label=excluded.device_label, last_seen=excluded.last_seen
            """,
            (endpoint, p256dh, auth, device_label, now, now),
        )
        row = c.execute(
            "SELECT id FROM push_subscriptions WHERE endpoint=?", (endpoint,)
        ).fetchone()
    return int(row[0]) if row else -1


def remove_subscription(endpoint: str) -> None:
    with longterm._conn() as c:
        c.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))


def list_subscriptions() -> list[dict]:
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id, endpoint, p256dh, auth, device_label, last_seen "
            "FROM push_subscriptions ORDER BY last_seen DESC"
        ).fetchall()
    return [
        {"id": r[0], "endpoint": r[1], "p256dh": r[2], "auth": r[3],
         "device_label": r[4], "last_seen": r[5]}
        for r in rows
    ]


# ── Notifier ─────────────────────────────────────────────────────────────────

class Notifier:
    def __init__(self) -> None:
        self._recent: dict[str, float] = {}
        self._lock = threading.Lock()
        self._tray_notify: Optional[Callable[[str, str], None]] = None

    def set_tray(self, fn: Optional[Callable[[str, str], None]]) -> None:
        """Optionally let the hub also raise a local desktop tray notification."""
        self._tray_notify = fn

    def notify(self, title: str, body: str, *, kind: str = "info",
               priority: str = "normal", url: Optional[str] = None,
               dedup_key: Optional[str] = None) -> None:
        """Fan a proactive message out to every device. Non-fatal on any error."""
        if dedup_key and self._is_duplicate(dedup_key):
            return
        payload = {
            "type": "notify", "title": title, "body": body, "kind": kind,
            "priority": priority, "url": url or "/", "ts": time.time(),
        }
        if dedup_key:
            payload["dedup_key"] = dedup_key

        self._safe(self._ws_broadcast, payload)
        sent_push = self._safe(self._web_push, payload) or 0
        if self._tray_notify:
            self._safe(lambda: self._tray_notify(title, body))
        # Telegram fallback only when no native push reached a device.
        if sent_push == 0 and getattr(config, "NOTIFY_TELEGRAM_FALLBACK", True):
            self._safe(self._telegram, title, body)

    # -- sinks ---------------------------------------------------------------

    def _ws_broadcast(self, payload: dict) -> None:
        from dashboard import server as _srv
        _srv.ws_manager.broadcast_threadsafe(payload)

    def _web_push(self, payload: dict) -> int:
        """Send to all subscribed devices. Returns count delivered. Prunes dead subs."""
        priv = getattr(config, "VAPID_PRIVATE_KEY", "")
        if not priv:
            return 0
        try:
            from pywebpush import webpush, WebPushException
        except Exception:
            return 0  # dependency absent → push disabled, other sinks still ran
        subs = list_subscriptions()
        if not subs:
            return 0
        data = json.dumps({
            "title": payload["title"], "body": payload["body"],
            "kind": payload["kind"], "priority": payload["priority"],
            "url": payload["url"], "dedup_key": payload.get("dedup_key"),
            "tag": payload.get("dedup_key") or payload["kind"],
        })
        claims_sub = getattr(config, "VAPID_SUBJECT", "mailto:apex@localhost")
        sent = 0
        for s in subs:
            info = {"endpoint": s["endpoint"],
                    "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}}
            try:
                webpush(subscription_info=info, data=data,
                        vapid_private_key=priv, vapid_claims={"sub": claims_sub})
                sent += 1
            except WebPushException as e:  # type: ignore[misc]
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):
                    remove_subscription(s["endpoint"])  # gone for good
            except Exception:
                pass
        return sent

    def _telegram(self, title: str, body: str) -> None:
        from tools import telegram as _tg
        if not _tg.is_configured():
            return
        text = f"*{title}*\n{body}"
        for chat_id in getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", []):
            try:
                _tg.send_message(chat_id, text)
            except Exception:
                pass

    # -- helpers -------------------------------------------------------------

    def _is_duplicate(self, key: str) -> bool:
        window = getattr(config, "NOTIFY_DEDUP_SECONDS", 30)
        now = time.time()
        with self._lock:
            # prune old keys opportunistically
            for k in [k for k, t in self._recent.items() if now - t > window]:
                self._recent.pop(k, None)
            if key in self._recent and now - self._recent[key] < window:
                return True
            self._recent[key] = now
            return False

    @staticmethod
    def _safe(fn: Callable, *args):
        try:
            return fn(*args)
        except Exception as e:
            print(f"[Notify] sink error: {e}")
            return None


# ── Module-level singleton ───────────────────────────────────────────────────

_notifier = Notifier()


def get_notifier() -> Notifier:
    return _notifier


def notify(title: str, body: str, **kwargs) -> None:
    _notifier.notify(title, body, **kwargs)


def set_tray(fn: Optional[Callable[[str, str], None]]) -> None:
    _notifier.set_tray(fn)
