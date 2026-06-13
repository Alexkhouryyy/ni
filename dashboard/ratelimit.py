"""Tiny in-memory per-IP auth-failure throttle.

Deliberately dependency-free so it can be unit-tested without importing the whole
FastAPI server. Used by the dashboard auth middleware to cool off an IP that
keeps presenting bad tokens (brute-force protection on a publicly-exposed Apex).
"""
from __future__ import annotations

import time


class AuthThrottle:
    def __init__(self, window: float = 60.0, max_fails: int = 10):
        self.window = window
        self.max_fails = max_fails
        self._fails: dict[str, list[float]] = {}

    def _live(self, ip: str, now: float) -> list[float]:
        return [t for t in self._fails.get(ip, []) if now - t < self.window]

    def record_failure(self, ip: str, now: float | None = None) -> bool:
        """Record a failed auth from ip. Returns True if ip is now locked out."""
        now = time.time() if now is None else now
        fails = self._live(ip, now)
        fails.append(now)
        self._fails[ip] = fails
        return len(fails) > self.max_fails

    def is_locked(self, ip: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return len(self._live(ip, now)) > self.max_fails

    def reset(self, ip: str) -> None:
        self._fails.pop(ip, None)
