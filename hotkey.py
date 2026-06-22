"""
JARVIS Screen Vision Hotkey — global OS-level keyboard shortcut.

Press anywhere on the OS (VSCode, Chrome, terminal, a PDF) to have JARVIS
take a screenshot, analyze it with the vision model, and speak a response
through the existing TTS + WebSocket pipeline.

The hotkey press IS the permission. No always-on watching.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

log = logging.getLogger("jarvis.hotkey")


class ScreenHotkey:
    """Thin wrapper around pynput.keyboard.GlobalHotKeys with an asyncio bridge.

    The pynput listener fires on its own thread; we forward into the main
    asyncio loop via run_coroutine_threadsafe.
    """

    def __init__(
        self,
        combo: str,
        on_trigger: Callable[[], Awaitable[None]],
        loop: asyncio.AbstractEventLoop,
        debounce_seconds: float = 2.0,
    ):
        self.combo = combo                  # e.g. "<ctrl>+<shift>+j"
        self.on_trigger = on_trigger        # async callable
        self.loop = loop
        self.debounce_seconds = debounce_seconds
        self._listener = None               # pynput.keyboard.GlobalHotKeys
        self._last_fire = 0.0

    def _fire(self) -> None:
        now = time.monotonic()
        if now - self._last_fire < self.debounce_seconds:
            log.info("hotkey debounced")
            return
        self._last_fire = now
        log.info(f"hotkey fired ({self.combo})")
        try:
            asyncio.run_coroutine_threadsafe(self.on_trigger(), self.loop)
        except Exception as e:
            log.warning(f"hotkey dispatch failed: {e}")

    def start(self) -> bool:
        """Start the OS-level listener. Returns True on success."""
        try:
            from pynput import keyboard  # type: ignore
        except ImportError:
            log.warning("pynput not installed — run: pip install pynput")
            return False

        try:
            self._listener = keyboard.GlobalHotKeys({self.combo: self._fire})
            self._listener.start()
            log.info(f"Screen hotkey listening on {self.combo}")
            return True
        except Exception as e:
            log.warning(f"failed to start hotkey listener on {self.combo}: {e}")
            self._listener = None
            return False

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as e:
                log.warning(f"failed to stop hotkey listener: {e}")
            self._listener = None
            log.info("Screen hotkey listener stopped")

    def rebind(self, new_combo: str) -> bool:
        """Stop the existing listener and start a new one on a different combo."""
        self.stop()
        self.combo = new_combo
        return self.start()

    @property
    def running(self) -> bool:
        return self._listener is not None
