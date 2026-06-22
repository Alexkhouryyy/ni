"""
JARVIS Proactive Loop.

A background async task that watches the user's state (calendar, tasks,
weather) and pushes unsolicited audio when something deserves attention.

Design notes:
- Triggers are pure-Python (no LLM, no vision). They return either None or
  a (trigger_id, line) tuple. The line is spoken as-is — JARVIS personality
  is baked into the trigger templates.
- Cost shape: zero API calls per tick unless something fires; if it fires,
  exactly one OpenAI TTS call. No Claude calls ever from this module.
- Anti-spam: each (trigger_id) gets a cooldown so the same meeting / task /
  weather shift isn't announced repeatedly.
- Kill switch: PROACTIVE_ENABLED=false in env disables everything. Can be
  toggled live without restart via /api/settings/preferences.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

log = logging.getLogger("jarvis.proactive")

# Tick cadence — how often to evaluate triggers.
TICK_SECONDS = 60

# Per-trigger cooldowns (seconds). Keys are bare trigger names; the suffix
# after ":" in trigger_id (e.g. event id) is the entity ID — full trigger_id
# is what the cooldown dict actually keys on. The DEFAULTS below apply to
# trigger families that don't have their own entry.
COOLDOWNS = {
    "meeting_10min": 30 * 60,    # 30 min — re-announce if event is rescheduled
    "meeting_2min":  30 * 60,
    "conflict":      6 * 60 * 60,  # 6h
    "overdue_task":  4 * 60 * 60,  # 4h
    "weather_shift": 3 * 60 * 60,  # 3h
}
DEFAULT_COOLDOWN = 60 * 60


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

async def _check_meetings(now: datetime) -> list[tuple[str, str]]:
    """Return (trigger_id, line) for any meetings near 10-min or 2-min mark."""
    try:
        from calendar_access import get_upcoming_events
    except Exception as e:
        log.debug(f"calendar import failed: {e}")
        return []

    try:
        events = await get_upcoming_events(hours=1)
    except Exception as e:
        log.debug(f"calendar fetch failed: {e}")
        return []

    fires: list[tuple[str, str]] = []
    for ev in events:
        start = ev.get("start_dt")
        title = ev.get("title", "your next meeting")
        if not isinstance(start, datetime):
            continue

        # Normalize tz so we can subtract
        if start.tzinfo is None:
            start_cmp = start
            now_cmp = now.replace(tzinfo=None) if now.tzinfo else now
        else:
            start_cmp = start
            now_cmp = now if now.tzinfo else now.replace(tzinfo=timezone.utc)

        delta_min = (start_cmp - now_cmp).total_seconds() / 60
        ev_key = f"{ev.get('start','')}|{title}"

        if 9.0 <= delta_min <= 11.0:
            fires.append((
                f"meeting_10min:{ev_key}",
                f"Sir, your {title} starts in ten minutes.",
            ))
        elif 1.5 <= delta_min <= 2.5:
            fires.append((
                f"meeting_2min:{ev_key}",
                f"Two minutes to {title}, sir. Shall I pull up the agenda?",
            ))
    return fires


def _check_overdue_tasks(now: datetime) -> list[tuple[str, str]]:
    """Return overdue-task announcements."""
    try:
        from memory import get_open_tasks
    except Exception as e:
        log.debug(f"memory import failed: {e}")
        return []

    try:
        tasks = get_open_tasks()
    except Exception as e:
        log.debug(f"task fetch failed: {e}")
        return []

    fires: list[tuple[str, str]] = []
    today = now.date()
    for t in tasks:
        due = t.get("due_date")
        if not due:
            continue
        try:
            due_d = datetime.strptime(due, "%Y-%m-%d").date()
        except Exception:
            continue
        if due_d >= today:
            continue
        days_late = (today - due_d).days
        title = t.get("title", "a task")
        tid = t.get("id", "?")
        plural = "day" if days_late == 1 else "days"
        fires.append((
            f"overdue_task:{tid}",
            f"The {title} is {days_late} {plural} overdue, sir.",
        ))
    return fires


# Weather state — we cache the last temperature so we can detect shifts.
_last_weather_temp: Optional[float] = None


def _parse_temp_f(weather_str: str) -> Optional[float]:
    """Try to extract a Fahrenheit temperature from a weather context string."""
    if not weather_str:
        return None
    import re
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*°?\s*F", weather_str)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def _check_weather_shift(get_weather: Callable[[], str]) -> list[tuple[str, str]]:
    """Detect a >=10°F (~5°C) shift since the last reading."""
    global _last_weather_temp
    try:
        weather = get_weather() or ""
    except Exception:
        return []

    temp = _parse_temp_f(weather)
    if temp is None:
        return []

    if _last_weather_temp is None:
        _last_weather_temp = temp
        return []

    delta = temp - _last_weather_temp
    if abs(delta) < 10:  # ~5.5°C
        return []

    direction = "dropped" if delta < 0 else "climbed"
    bucket = int(temp // 10)  # use temp bucket so the trigger_id changes meaningfully
    line = (
        f"The temperature has {direction} to {temp:.0f} degrees, sir. "
        "You may want to dress accordingly."
    )
    _last_weather_temp = temp
    return [(f"weather_shift:{bucket}", line)]


# ---------------------------------------------------------------------------
# Cooldown + push
# ---------------------------------------------------------------------------

def _on_cooldown(cooldown: dict[str, float], trigger_id: str, now: float) -> bool:
    last = cooldown.get(trigger_id)
    if last is None:
        return False
    family = trigger_id.split(":", 1)[0]
    interval = COOLDOWNS.get(family, DEFAULT_COOLDOWN)
    return (now - last) < interval


async def _push_proactive_line(ws, line: str, synthesize_fn) -> None:
    """Speak a single proactive line through the WebSocket."""
    try:
        audio = await synthesize_fn(line)
        await ws.send_json({"type": "status", "state": "speaking"})
        if audio:
            encoded = base64.b64encode(audio).decode()
            await ws.send_json({"type": "audio", "data": encoded, "text": line})
        else:
            await ws.send_json({"type": "text", "text": line})
        await ws.send_json({"type": "status", "state": "idle"})
        log.info(f"proactive fired: {line}")
    except Exception as e:
        log.warning(f"proactive push failed: {e}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def proactive_loop(
    get_active_ws: Callable[[], object],
    get_voice_state: Callable[[], Optional[dict]],
    get_weather: Callable[[], str],
    synthesize_fn: Callable[[str], Awaitable[Optional[bytes]]],
) -> None:
    """Main proactive loop. Runs forever; exceptions per-tick are swallowed."""
    log.info("proactive loop starting")
    cooldown: dict[str, float] = {}

    while True:
        try:
            await asyncio.sleep(TICK_SECONDS)

            if os.getenv("PROACTIVE_ENABLED", "true").lower() not in ("true", "1", "yes"):
                continue

            ws = get_active_ws()
            if ws is None:
                continue

            # Voice collision — skip if user spoke recently
            vs = get_voice_state()
            if vs and (time.time() - vs.get("last_user_time", 0)) < 8:
                log.debug("proactive: voice collision skip")
                continue

            now_dt = datetime.now()

            fires: list[tuple[str, str]] = []
            try:
                fires.extend(await _check_meetings(now_dt))
            except Exception as e:
                log.debug(f"meeting check failed: {e}")
            try:
                fires.extend(_check_overdue_tasks(now_dt))
            except Exception as e:
                log.debug(f"task check failed: {e}")
            try:
                fires.extend(_check_weather_shift(get_weather))
            except Exception as e:
                log.debug(f"weather check failed: {e}")

            if not fires:
                continue

            now_ts = time.time()
            for trigger_id, line in fires:
                if _on_cooldown(cooldown, trigger_id, now_ts):
                    continue
                cooldown[trigger_id] = now_ts
                await _push_proactive_line(ws, line, synthesize_fn)
                # Brief pause between back-to-back fires so they don't pile up
                await asyncio.sleep(2.0)

        except asyncio.CancelledError:
            log.info("proactive loop cancelled")
            raise
        except Exception as e:
            log.error(f"proactive loop tick failed: {e}", exc_info=True)
