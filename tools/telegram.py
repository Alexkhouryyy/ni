"""Telegram bot channel — inbound/outbound messages.

Outbound:
  - send_message(chat_id, text): POST to Telegram Bot API

Inbound:
  Telegram delivers updates to POST /telegram/webhook (wired in dashboard/server.py).
  Each update is routed through dispatch_inbound(), which runs the agent
  and sends the reply back to Telegram.

Setup:
  1. Create a bot via @BotFather, get the token.
  2. Set TELEGRAM_BOT_TOKEN in .env (and optionally TELEGRAM_ALLOWED_CHAT_IDS).
  3. Register the webhook once:
       curl "https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://your.host/telegram/webhook"
"""
import json
from typing import Callable, Optional

import config

_agent_run_fn: Optional[Callable] = None


def set_agent_run_fn(fn: Callable) -> None:
    global _agent_run_fn
    _agent_run_fn = fn


def _token() -> str:
    return getattr(config, "TELEGRAM_BOT_TOKEN", "") or ""


def is_configured() -> bool:
    return bool(_token())


def _allowed_ids() -> set[int]:
    raw = getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", []) or []
    try:
        return {int(x) for x in raw if str(x).strip().lstrip("-").isdigit()}
    except Exception:
        return set()


def _is_allowed(chat_id: int) -> bool:
    allowed = _allowed_ids()
    return not allowed or chat_id in allowed


def send_message(chat_id: int | str, text: str) -> str:
    if not is_configured():
        return "[Telegram] TELEGRAM_BOT_TOKEN not configured."
    import urllib.request
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_token()}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                return f"Telegram message sent to chat_id={chat_id}"
            return f"[Telegram] API error: {result}"
    except Exception as e:
        return f"[Telegram] send_message failed: {e}"


def dispatch_inbound(update: dict) -> Optional[str]:
    """Process one Telegram update dict. Sends reply via API. Returns reply text or None."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None

    chat_id: int = msg.get("chat", {}).get("id")
    text: str = (msg.get("text") or "").strip()
    username: str = msg.get("from", {}).get("username", "unknown")

    if not chat_id or not text:
        return None

    if not _is_allowed(chat_id):
        send_message(chat_id, "Sorry, this chat is not authorized.")
        return None

    if _agent_run_fn is None:
        send_message(chat_id, "Agent not ready yet. Try again in a moment.")
        return None

    try:
        reply = _agent_run_fn(
            f"[Telegram from @{username}] {text}",
            channel_id=f"telegram:{chat_id}",
        )
    except Exception as e:
        reply = f"Agent error: {e}"

    if len(reply) > 4096:
        reply = reply[:4090] + "…"

    send_message(chat_id, reply)
    return reply
