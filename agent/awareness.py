"""Continuous awareness — event-driven watchers replace periodic screen polling.

Watchers (each in its own thread):
  - Active window (xdotool getactivewindow getwindowname): app switch events
  - Clipboard (pyperclip): text the user copies
  - File watcher (watchdog): user-configured directories
  - Screen (mss): periodic screenshot (kept from old proactive monitor)

All events flow into an AwarenessLog ring buffer. Every N seconds, a lightweight
Haiku call reviews recent events and decides whether to interrupt the user with
a proactive observation.
"""
import os
import subprocess
import threading
import time
from collections import deque
from typing import Callable, Optional

import config

# Try imports — degrade gracefully
try:
    import pyperclip
except Exception:
    pyperclip = None

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG = True
except Exception:
    _WATCHDOG = False


class AwarenessLog:
    """Ring buffer of recent events."""
    def __init__(self, maxlen: int = 60):
        self._events: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, source: str, content: str) -> None:
        with self._lock:
            self._events.append({"ts": time.time(), "source": source, "content": content})

    def recent(self, since_seconds: float = 120.0) -> list[dict]:
        cutoff = time.time() - since_seconds
        with self._lock:
            return [e for e in self._events if e["ts"] >= cutoff]

    def drain(self) -> list[dict]:
        with self._lock:
            items = list(self._events)
            self._events.clear()
            return items


class ActiveWindowWatcher(threading.Thread):
    def __init__(self, log: AwarenessLog, interval: float = 2.0):
        super().__init__(daemon=True, name="WindowWatcher")
        self.log = log
        self.interval = interval
        self._stop = threading.Event()
        self._last_title: str = ""

    def stop(self): self._stop.set()

    def run(self):
        while not self._stop.wait(timeout=self.interval):
            try:
                wid = subprocess.run(
                    ["xdotool", "getactivewindow"],
                    capture_output=True, text=True, timeout=2,
                ).stdout.strip()
                if not wid:
                    continue
                title = subprocess.run(
                    ["xdotool", "getwindowname", wid],
                    capture_output=True, text=True, timeout=2,
                ).stdout.strip()
                if title and title != self._last_title:
                    self.log.add("window", f"Switched to: {title}")
                    self._last_title = title
            except Exception:
                continue


class ClipboardWatcher(threading.Thread):
    def __init__(self, log: AwarenessLog, interval: float = 1.5):
        super().__init__(daemon=True, name="ClipboardWatcher")
        self.log = log
        self.interval = interval
        self._stop = threading.Event()
        self._last: str = ""

    def stop(self): self._stop.set()

    def run(self):
        if pyperclip is None:
            return
        while not self._stop.wait(timeout=self.interval):
            try:
                current = pyperclip.paste()
                if current and current != self._last and len(current) < 4000:
                    self._last = current
                    snippet = current[:200] + ("..." if len(current) > 200 else "")
                    self.log.add("clipboard", f"Copied: {snippet}")
            except Exception:
                continue


class FileWatcher(threading.Thread):
    def __init__(self, log: AwarenessLog, paths: list[str]):
        super().__init__(daemon=True, name="FileWatcher")
        self.log = log
        self.paths = paths
        self._observer = None

    def stop(self):
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass

    def run(self):
        if not _WATCHDOG or not self.paths:
            return

        log = self.log

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.is_directory:
                    return
                log.add("file", f"Modified: {event.src_path}")
            def on_created(self, event):
                if event.is_directory:
                    return
                log.add("file", f"Created: {event.src_path}")

        self._observer = Observer()
        handler = Handler()
        for p in self.paths:
            expanded = os.path.expanduser(p)
            if os.path.exists(expanded):
                self._observer.schedule(handler, expanded, recursive=True)
        self._observer.start()
        # Keep thread alive until observer stopped
        while self._observer.is_alive():
            time.sleep(1)


class AwarenessMonitor:
    """Coordinates watchers and triggers proactive speech-up when warranted."""

    def __init__(
        self,
        agent_proactive_check: Callable[[str], Optional[str]],
        speak_fn: Callable[[str], None],
        watch_paths: Optional[list[str]] = None,
        review_interval: float = 60.0,
    ):
        self.log = AwarenessLog()
        self.proactive_check = agent_proactive_check  # signature: (events_summary) -> str|None
        self.speak = speak_fn
        self.review_interval = review_interval
        self._stop = threading.Event()
        self._reviewer: Optional[threading.Thread] = None

        # Watchers
        self.window = ActiveWindowWatcher(self.log)
        self.clipboard = ClipboardWatcher(self.log)
        self.files = FileWatcher(self.log, watch_paths or [])

        # IoT watcher — only starts if env flag is set and entities are configured
        self.iot: Optional[threading.Thread] = None
        if config.IOT_ENABLED and config.IOT_AWARENESS_ENTITIES:
            from agent.iot_watcher import IoTWatcher
            self.iot = IoTWatcher(self.log)

    def start(self) -> None:
        self.window.start()
        self.clipboard.start()
        self.files.start()
        if self.iot is not None:
            self.iot.start()
        self._reviewer = threading.Thread(target=self._review_loop, daemon=True, name="AwarenessReviewer")
        self._reviewer.start()
        print(f"[Awareness] Monitor started (review every {self.review_interval}s).")

    def stop(self) -> None:
        self._stop.set()
        self.window.stop()
        self.clipboard.stop()
        self.files.stop()
        if self.iot is not None:
            self.iot.stop()

    def _review_loop(self) -> None:
        last_summary = ""
        while not self._stop.wait(timeout=self.review_interval):
            events = self.log.recent(since_seconds=self.review_interval * 1.5)
            if not events:
                continue
            summary = "\n".join(
                f"[{e['source']}] {e['content']}" for e in events[-20:]
            )
            try:
                observation = self.proactive_check(summary)
                if observation and observation != last_summary:
                    last_summary = observation
                    print(f"[Awareness] Speaking up: {observation}")
                    self.speak(f"Heads up. {observation}")
            except Exception as e:
                print(f"[Awareness] Review error: {e}")
