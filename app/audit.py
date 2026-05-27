"""Wake-event audit log — privacy/trust layer.

Every wake-word firing writes one line to ~/.apex/wake_audit.log so the user
can verify exactly what Apex heard and how it responded. The log is
human-readable, never auto-deleted, and grows on the order of KB/day.
"""
import os
import time
from typing import Literal

import config

Action = Literal["responded", "muted_ignored", "paused_ignored", "no_continuation"]


def _ensure_dir() -> None:
    path = config.RESIDENT_AUDIT_FILE
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def record(transcript: str, action: Action, *, note: str = "") -> None:
    """Append one audit entry. Best-effort — errors are swallowed so audit
    failures never break the wake path."""
    try:
        _ensure_dir()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        # One line per event, pipe-delimited, transcript escaped
        safe = transcript.replace("|", "/").replace("\n", " ")[:300]
        suffix = f" | note={note}" if note else ""
        line = f"{ts} | action={action} | heard={safe!r}{suffix}\n"
        with open(config.RESIDENT_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def recent(limit: int = 50) -> list[dict]:
    """Read the most recent audit entries (for dashboard display)."""
    try:
        if not os.path.exists(config.RESIDENT_AUDIT_FILE):
            return []
        with open(config.RESIDENT_AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out: list[dict] = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            entry: dict = {"raw": line}
            for p in parts:
                if "=" in p:
                    k, _, v = p.partition("=")
                    entry[k.strip()] = v.strip()
                else:
                    entry["ts"] = p
            out.append(entry)
        return list(reversed(out))
    except Exception:
        return []
