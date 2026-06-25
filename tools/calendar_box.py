"""Calendar tool — read-only CalDAV event access.

Reads upcoming events from any CalDAV server (iCloud, Fastmail, Nextcloud,
Google via app password, etc.) so Apex can answer "what's on my calendar" and
fire proactive "meeting in 10 minutes" alerts.

Read-only by design — no event creation (keeps risk low). Creating events can be
added later behind the approval gate, like email sending.

Config (see config.py / .env):
  CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD
Requires the `caldav` package (pip install caldav). Degrades gracefully if absent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date, timezone
from typing import Optional


def _cfg() -> dict:
    import config
    return {
        "url": getattr(config, "CALDAV_URL", "") or "",
        "username": getattr(config, "CALDAV_USERNAME", "") or "",
        "password": getattr(config, "CALDAV_PASSWORD", "") or "",
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["url"] and c["username"] and c["password"])


def _to_dt(value) -> Optional[datetime]:
    """Normalize an icalendar dtstart/dtend value to an aware datetime (UTC)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return None


def upcoming_events(days_ahead: int = 7, limit: int = 50) -> list[dict]:
    """Return events between now and now+days_ahead, soonest first."""
    if not is_configured():
        return [{"error": "Calendar not configured. Set CALDAV_URL / CALDAV_USERNAME / CALDAV_PASSWORD in .env."}]
    try:
        import caldav
    except Exception:
        return [{"error": "The 'caldav' package isn't installed. Run: pip install caldav"}]

    c = _cfg()
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)
    out: list[dict] = []
    try:
        client = caldav.DAVClient(url=c["url"], username=c["username"], password=c["password"])
        principal = client.principal()
        for cal in principal.calendars():
            try:
                found = cal.search(start=now, end=end, event=True, expand=True)
            except Exception:
                # Older servers don't support expand — fall back to date_search.
                try:
                    found = cal.date_search(start=now, end=end)
                except Exception:
                    continue
            for ev in found:
                try:
                    comp = ev.icalendar_component
                    start = _to_dt(getattr(comp.get("dtstart"), "dt", None))
                    if start is None:
                        continue
                    end_dt = _to_dt(getattr(comp.get("dtend"), "dt", None))
                    all_day = not isinstance(getattr(comp.get("dtstart"), "dt", None), datetime)
                    starts_in = (start - now).total_seconds()
                    out.append({
                        "summary": str(comp.get("summary", "(no title)")),
                        "start": start.isoformat(),
                        "end": end_dt.isoformat() if end_dt else None,
                        "location": str(comp.get("location", "")) or None,
                        "all_day": all_day,
                        "starts_in_min": int(starts_in / 60),
                        "calendar": str(getattr(cal, "name", "") or ""),
                    })
                except Exception:
                    continue
    except Exception as e:
        return [{"error": f"CalDAV error: {e}"}]

    out = [e for e in out if "error" not in e]
    out.sort(key=lambda e: e["start"])
    return out[:limit]


def imminent_events(within_minutes: int = 10) -> list[dict]:
    """Events starting within the next `within_minutes` (for proactive alerts)."""
    evs = upcoming_events(days_ahead=1, limit=50)
    if evs and evs[0].get("error"):
        return []
    return [e for e in evs if e.get("all_day") is False and 0 < (e.get("starts_in_min") or 9999) <= within_minutes]
