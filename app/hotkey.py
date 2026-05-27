"""Global hotkey wrapper around pynput.

Press Ctrl+Space → wake Apex without speaking. Press Ctrl+Alt+M → toggle mute.
Both default combos are configurable via RESIDENT_GLOBAL_HOTKEY and
RESIDENT_MUTE_HOTKEY in config.py.

Degrades gracefully when pynput isn't installed or running headless — caller
just sees `start()` return False and continues.
"""
from typing import Callable, Optional


class GlobalHotkeys:
    """Owns a single pynput GlobalHotKeys listener with multiple bindings."""

    def __init__(self) -> None:
        self._listener: Optional[object] = None
        self._bindings: dict[str, Callable[[], None]] = {}

    def bind(self, combo: str, callback: Callable[[], None]) -> None:
        """Register a combo like '<ctrl>+<space>'. Must be called before start()."""
        self._bindings[combo] = callback

    def start(self) -> bool:
        if not self._bindings:
            return False
        try:
            from pynput import keyboard
        except ImportError:
            print("[Hotkey] pynput not installed — global hotkeys disabled. "
                  "Run: pip install pynput")
            return False

        try:
            self._listener = keyboard.GlobalHotKeys(self._bindings)
            self._listener.start()
            combos = ", ".join(self._bindings.keys())
            print(f"[Hotkey] Listening for: {combos}")
            return True
        except Exception as e:
            print(f"[Hotkey] Failed to start (likely no display / Wayland): {e}")
            return False

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
