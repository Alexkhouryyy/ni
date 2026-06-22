"""
JARVIS Mail Access — Gmail API (READ-ONLY + compose drafts).

Replaces the original Apple Mail / AppleScript implementation.
Exposes the same function signatures so server.py needs no changes.

READ-ONLY for inbox operations. Draft creation supported for reply workflow.
"""

import asyncio
import base64
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

log = logging.getLogger("jarvis.mail")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_service():
    """Return a Gmail API service object, or None if not authorized."""
    try:
        from googleapiclient.discovery import build
        from google_auth import get_credentials
        creds = get_credentials()
        if not creds:
            return None
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning(f"Gmail service unavailable: {e}")
        return None


def _decode_header_value(value: str) -> str:
    """Decode RFC2047-encoded header values."""
    try:
        from email.header import decode_header
        parts = decode_header(value)
        decoded = []
        for part, enc in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                decoded.append(str(part))
        return "".join(decoded)
    except Exception:
        return value


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return _decode_header_value(h.get("value", ""))
    return ""


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _extract_body(part)
            if text:
                return text
    return ""


def _parse_message(msg: dict) -> dict:
    """Normalize a Gmail message into JARVIS format."""
    headers = msg.get("payload", {}).get("headers", [])
    subject = _get_header(headers, "Subject") or "(No subject)"
    sender  = _get_header(headers, "From")
    date_str = _get_header(headers, "Date")
    snippet  = msg.get("snippet", "")
    body     = _extract_body(msg.get("payload", {}))

    try:
        dt = parsedate_to_datetime(date_str)
        date_fmt = dt.strftime("%b %d, %I:%M %p")
    except Exception:
        date_fmt = date_str

    return {
        "id":      msg.get("id", ""),
        "subject": subject,
        "sender":  sender,
        "date":    date_fmt,
        "snippet": snippet,
        "body":    (body or snippet)[:2000],
        "unread":  "UNREAD" in msg.get("labelIds", []),
    }


def _fetch_messages_sync(query: str = "", count: int = 10, label: str = "INBOX") -> list[dict]:
    """Synchronously fetch messages from Gmail."""
    service = _get_service()
    if not service:
        return []
    try:
        q = query
        if label == "UNREAD":
            q = ("is:unread " + q).strip()
        list_result = service.users().messages().list(
            userId="me",
            q=q or f"in:{label.lower()}",
            maxResults=count,
        ).execute()

        ids = [m["id"] for m in list_result.get("messages", [])]
        messages = []
        for msg_id in ids:
            try:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
                messages.append(_parse_message(msg))
            except Exception as e:
                log.debug(f"Failed to fetch message {msg_id}: {e}")
        return messages
    except Exception as e:
        log.warning(f"Gmail fetch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Public API (same signatures as original mail_access.py)
# ---------------------------------------------------------------------------

async def get_accounts() -> list[str]:
    """Return the authenticated Gmail address."""
    def _fetch():
        service = _get_service()
        if not service:
            return []
        try:
            profile = service.users().getProfile(userId="me").execute()
            return [profile.get("emailAddress", "")]
        except Exception:
            return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


async def get_unread_count() -> dict:
    """Return unread count per account."""
    def _fetch():
        service = _get_service()
        if not service:
            return {}
        try:
            profile = service.users().getProfile(userId="me").execute()
            email = profile.get("emailAddress", "Gmail")
            count = profile.get("messagesUnread", 0)
            return {email: count}
        except Exception as e:
            log.warning(f"Unread count failed: {e}")
            return {}
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


async def get_recent_messages(count: int = 10) -> list[dict]:
    """Return N most recent inbox messages."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_messages_sync, "", count, "INBOX")


async def get_unread_messages(count: int = 10) -> list[dict]:
    """Return N most recent unread messages."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_messages_sync, "is:unread", count, "INBOX")


async def get_messages_from_account(account_name: str, count: int = 10) -> list[dict]:
    """Return messages from a specific sender or account."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_messages_sync, f"from:{account_name}", count, "INBOX")


async def search_mail(query: str, count: int = 10) -> list[dict]:
    """Search Gmail with a query string."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_messages_sync, query, count, "INBOX")


async def read_message(subject_match: str) -> dict | None:
    """Find and return a message matching a subject string."""
    messages = await search_mail(f"subject:{subject_match}", count=1)
    return messages[0] if messages else None


# ---------------------------------------------------------------------------
# Formatting (same as original)
# ---------------------------------------------------------------------------

def format_unread_summary(unread: dict) -> str:
    if not unread:
        return "No unread mail."
    total = sum(unread.values())
    if total == 0:
        return "Inbox is clear."
    parts = [f"{count} unread in {acct}" for acct, count in unread.items() if count > 0]
    return "Mail: " + ", ".join(parts) + "."


def format_messages_for_context(messages: list[dict], label: str = "Recent emails") -> str:
    if not messages:
        return f"No {label.lower()}."
    lines = [f"{label}:"]
    for m in messages[:5]:
        sender = _short_sender(m.get("sender", ""))
        lines.append(f"  - From {sender}: \"{m['subject']}\" — {m['snippet'][:80]}")
    if len(messages) > 5:
        lines.append(f"  ... and {len(messages) - 5} more.")
    return "\n".join(lines)


def format_messages_for_voice(messages: list[dict]) -> str:
    if not messages:
        return "No messages."
    if len(messages) == 1:
        m = messages[0]
        return f"One message from {_short_sender(m['sender'])}: {m['subject']}."
    senders = list({_short_sender(m["sender"]) for m in messages[:3]})
    return (
        f"{len(messages)} messages. "
        f"From {', '.join(senders[:2])}"
        + (f" and others" if len(messages) > 2 else "") + "."
    )


def _short_sender(sender: str) -> str:
    """Extract display name or email from a full From: header."""
    if not sender:
        return "unknown"
    # "Display Name <email@example.com>" → "Display Name"
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        return match.group(1).strip()
    # bare email → local part
    match = re.match(r'([^@]+)@', sender.strip())
    if match:
        return match.group(1)
    return sender[:30]
