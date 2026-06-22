"""
JARVIS Calendar Access — Google Calendar API.

Replaces the original Apple Calendar / AppleScript implementation.
Exposes the same function signatures so server.py needs no changes.

Timezone: Asia/Beirut (GMT+3) per Alex's config.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger("jarvis.calendar")

USER_TZ = os.getenv("USER_TIMEZONE", "Asia/Beirut")

# In-memory cache
_event_cache: list[dict] = []
_cache_time: float = 0
_CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_service():
    """Return a Google Calendar service object, or None if not authorized."""
    try:
        from googleapiclient.discovery import build
        from google_auth import get_credentials
        creds = get_credentials()
        if not creds:
            return None
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning(f"Calendar service unavailable: {e}")
        return None


def _parse_event(item: dict) -> dict:
    """Normalize a Google Calendar event into JARVIS format."""
    start = item.get("start", {})
    end   = item.get("end", {})

    # Determine start datetime (all-day vs timed)
    start_str = start.get("dateTime") or start.get("date", "")
    end_str   = end.get("dateTime")   or end.get("date", "")

    try:
        if "T" in start_str:
            dt = datetime.fromisoformat(start_str)
            start_fmt = dt.strftime("%-I:%M %p") if os.name != "nt" else dt.strftime("%I:%M %p").lstrip("0")
        else:
            dt = datetime.fromisoformat(start_str)
            start_fmt = "All day"
    except Exception:
        dt = datetime.now()
        start_fmt = start_str

    return {
        "title":    item.get("summary", "(No title)"),
        "start":    start_str,
        "end":      end_str,
        "start_dt": dt,
        "start_fmt": start_fmt,
        "location": item.get("location", ""),
        "description": item.get("description", ""),
        "calendar": item.get("organizer", {}).get("displayName", ""),
        "attendees": [
            a.get("email", "") for a in item.get("attendees", [])
        ],
        "hangout_link": item.get("hangoutLink", "") or item.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", ""),
    }


def _fetch_events_sync(hours_ahead: int = 24) -> list[dict]:
    """Synchronous fetch from Google Calendar (called from executor)."""
    service = _get_service()
    if not service:
        return []

    try:
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(hours=hours_ahead)).isoformat()

        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        items = result.get("items", [])
        return [_parse_event(i) for i in items]
    except Exception as e:
        log.warning(f"Calendar fetch failed: {e}")
        return []


async def _fetch_events(hours_ahead: int = 24) -> list[dict]:
    """Async wrapper around synchronous Google Calendar fetch."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_events_sync, hours_ahead)


# ---------------------------------------------------------------------------
# Public API (same signatures as original calendar_access.py)
# ---------------------------------------------------------------------------

async def refresh_cache():
    """Refresh the in-memory event cache."""
    global _event_cache, _cache_time
    import time
    events = await _fetch_events(hours_ahead=48)
    _event_cache = events
    _cache_time = time.time()
    log.debug(f"Calendar cache refreshed: {len(events)} events")


async def get_todays_events() -> list[dict]:
    """Return events happening today (local date)."""
    import time
    global _event_cache, _cache_time

    if not _event_cache or (time.time() - _cache_time > _CACHE_TTL):
        await refresh_cache()

    today = datetime.now().date()
    return [
        e for e in _event_cache
        if e["start_dt"].date() == today
    ]


async def get_upcoming_events(hours: int = 4) -> list[dict]:
    """Return events in the next N hours."""
    import time
    global _event_cache, _cache_time

    if not _event_cache or (time.time() - _cache_time > _CACHE_TTL):
        await refresh_cache()

    cutoff = datetime.now(timezone.utc) + timedelta(hours=hours)
    now    = datetime.now(timezone.utc)

    result = []
    for e in _event_cache:
        try:
            dt = e["start_dt"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if now <= dt <= cutoff:
                result.append(e)
        except Exception:
            pass
    return result


async def get_next_event() -> dict | None:
    """Return the very next upcoming event."""
    events = await get_upcoming_events(hours=24)
    return events[0] if events else None


async def get_calendar_names() -> list[str]:
    """Return list of accessible calendar names."""
    def _fetch():
        service = _get_service()
        if not service:
            return []
        try:
            result = service.calendarList().list().execute()
            return [c.get("summary", "") for c in result.get("items", [])]
        except Exception as e:
            log.warning(f"Calendar list failed: {e}")
            return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


# ---------------------------------------------------------------------------
# Formatting (same as original)
# ---------------------------------------------------------------------------

def format_events_for_context(events: list[dict]) -> str:
    if not events:
        return "No upcoming events."
    lines = ["Upcoming calendar events:"]
    for e in events:
        line = f"  - {e['start_fmt']}: {e['title']}"
        if e.get("location"):
            line += f" @ {e['location']}"
        if e.get("hangout_link"):
            line += " [video call]"
        lines.append(line)
    return "\n".join(lines)


def format_schedule_summary(events: list[dict]) -> str:
    if not events:
        return "Your calendar is clear."
    if len(events) == 1:
        e = events[0]
        return f"One event today: {e['title']} at {e['start_fmt']}."
    titles = [f"{e['title']} at {e['start_fmt']}" for e in events[:3]]
    suffix = f" and {len(events) - 3} more" if len(events) > 3 else ""
    return "Today: " + ", ".join(titles) + suffix + "."
