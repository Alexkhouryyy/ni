"""
JARVIS Desktop Shell — Always-On-Top Floating Orb.

Wraps the existing Vite frontend in a borderless, transparent, always-on-top
native window. JARVIS lives on your desktop as a small glowing orb in the
corner, expandable to a full chat panel on click.

One command to rule them all:
    python desktop_shell.py

It will:
1. Auto-spawn the backend (server.py) if not already running
2. Auto-spawn the frontend (npm run dev) if not already running
3. Open the orb window pointing at the frontend
4. Register a system-tray icon (Show / Hide / Quit)
5. Register a global hotkey to toggle visibility (default Ctrl+Shift+\\)
6. Remember the orb's position across restarts (~/.jarvis/window.json)

Close the tray icon → graceful shutdown of backend + frontend + shell.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
STATE_DIR = Path.home() / ".jarvis"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# When launched via pythonw.exe there is no console, so log to a file.
_SHELL_LOG = STATE_DIR / "logs"
_SHELL_LOG.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(_SHELL_LOG / "shell.log", encoding="utf-8"),
        logging.StreamHandler(),  # harmless when a console exists, ignored otherwise
    ],
)
log = logging.getLogger("jarvis.shell")

# pywebview floods the log with harmless WebView2 accessibility-probe warnings
# on frameless+transparent windows. Silence it — it's cosmetic noise.
logging.getLogger("pywebview").setLevel(logging.CRITICAL)

WINDOW_STATE_FILE = STATE_DIR / "window.json"
TRAY_ICON_PATH = PROJECT_DIR / "assets" / "jarvis-tray.png"

BACKEND_URL_HEALTH = "https://localhost:8340/api/health"
BACKEND_PORT = 8340
FRONTEND_URL = os.environ.get("DESKTOP_SHELL_FRONTEND_URL", "http://localhost:5195")
FRONTEND_PORT = int(FRONTEND_URL.rsplit(":", 1)[-1].strip("/"))

COLLAPSED_SIZE = (140, 140)
EXPANDED_SIZE = (440, 640)
DEFAULT_HOTKEY = os.environ.get("DESKTOP_SHELL_HOTKEY", "<ctrl>+<shift>+\\")


# ---------------------------------------------------------------------------
# Subprocess management — auto-spawn backend + frontend if not already up
# ---------------------------------------------------------------------------

def _is_port_listening(port: int, timeout: float = 1.0) -> bool:
    """Probe IPv4 and IPv6 localhost — Vite binds IPv6-only by default on Windows."""
    import socket
    for family, host in [(socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")]:
        s = socket.socket(family, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            continue
        finally:
            s.close()
    return False


def _wait_for_port(port: int, timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _is_port_listening(port):
            return True
        time.sleep(0.5)
    return False


# Windows flag: run a process with NO console window at all
_CREATE_NO_WINDOW = 0x08000000

# Engine-room logs go here so we can debug even though no window is shown
LOG_DIR = STATE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class ServiceManager:
    """Spawns and manages backend + frontend subprocesses — invisibly.

    No console windows are ever shown. Each engine's output is redirected to
    a log file under ~/.jarvis/logs/ so problems are still debuggable.
    Shutdown kills the whole process tree so nothing is orphaned.
    """

    def __init__(self):
        self.backend_proc: Optional[subprocess.Popen] = None
        self.frontend_proc: Optional[subprocess.Popen] = None
        self._backend_log = None
        self._frontend_log = None

    def _spawn_hidden(self, cmd, cwd: str, log_path: Path, shell: bool = False):
        """Start a process with no visible window, output piped to a log file."""
        log_f = open(log_path, "a", encoding="utf-8", errors="replace")
        log_f.write(f"\n\n===== started {datetime.now().isoformat()} =====\n")
        log_f.flush()
        flags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            shell=shell,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        return proc, log_f

    def ensure_backend(self) -> None:
        if _is_port_listening(BACKEND_PORT):
            log.info(f"Backend already running on {BACKEND_PORT}")
            return
        log.info("Starting backend (hidden)...")
        self.backend_proc, self._backend_log = self._spawn_hidden(
            [sys.executable, str(PROJECT_DIR / "server.py")],
            cwd=str(PROJECT_DIR),
            log_path=LOG_DIR / "backend.log",
        )

    def ensure_frontend(self) -> None:
        if _is_port_listening(FRONTEND_PORT):
            log.info(f"Frontend already running on {FRONTEND_PORT}")
            return
        log.info("Starting frontend (hidden)...")
        cmd = ["npm", "run", "dev", "--", "--host", "0.0.0.0",
               "--port", str(FRONTEND_PORT), "--strictPort"]
        self.frontend_proc, self._frontend_log = self._spawn_hidden(
            cmd,
            cwd=str(PROJECT_DIR / "frontend"),
            log_path=LOG_DIR / "frontend.log",
            shell=(sys.platform == "win32"),  # npm is npm.cmd on Windows
        )

    def is_backend_alive(self) -> bool:
        return _is_port_listening(BACKEND_PORT)

    def is_frontend_alive(self) -> bool:
        return _is_port_listening(FRONTEND_PORT)

    def wait_ready(self) -> bool:
        log.info(f"Waiting for backend on :{BACKEND_PORT}...")
        if not _wait_for_port(BACKEND_PORT, timeout_seconds=45):
            log.error("Backend failed to come up.")
            return False
        log.info(f"Waiting for frontend on :{FRONTEND_PORT}...")
        if not _wait_for_port(FRONTEND_PORT, timeout_seconds=45):
            log.error("Frontend failed to come up.")
            return False
        return True

    def _kill_tree(self, proc: Optional[subprocess.Popen], name: str) -> None:
        """Kill a process AND all its children (npm spawns a tree)."""
        if proc is None:
            return
        try:
            if proc.poll() is not None:
                return  # already dead
            log.info(f"Stopping {name} (pid {proc.pid})...")
            if sys.platform == "win32":
                # /T = kill the whole tree, /F = force
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    creationflags=_CREATE_NO_WINDOW,
                    capture_output=True,
                )
            else:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as e:
            log.warning(f"Failed to stop {name}: {e}")

    def shutdown(self) -> None:
        self._kill_tree(self.frontend_proc, "frontend")
        self._kill_tree(self.backend_proc, "backend")
        for f in (self._backend_log, self._frontend_log):
            try:
                if f:
                    f.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Window-position persistence
# ---------------------------------------------------------------------------

def _load_window_state() -> dict:
    try:
        if WINDOW_STATE_FILE.exists():
            return json.loads(WINDOW_STATE_FILE.read_text())
    except Exception as e:
        log.warning(f"Failed to load window state: {e}")
    return {}


def _save_window_state(x: int, y: int) -> None:
    try:
        WINDOW_STATE_FILE.write_text(json.dumps({"x": x, "y": y}))
    except Exception as e:
        log.warning(f"Failed to save window state: {e}")


# ---------------------------------------------------------------------------
# Tray icon (pystray)
# ---------------------------------------------------------------------------

def _build_tray_icon():
    """Generate a simple JARVIS arc-reactor-style icon if none exists."""
    from PIL import Image, ImageDraw

    if TRAY_ICON_PATH.exists():
        return Image.open(TRAY_ICON_PATH)

    TRAY_ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Outer ring
    d.ellipse((4, 4, 60, 60), outline=(0, 200, 255, 255), width=3)
    # Inner core
    d.ellipse((20, 20, 44, 44), fill=(0, 220, 255, 255))
    img.save(TRAY_ICON_PATH)
    return img


# ---------------------------------------------------------------------------
# The shell class — JS API + window control + tray
# ---------------------------------------------------------------------------

class JarvisShell:
    """Bridges the pywebview window, tray, hotkey, and subprocess lifetimes."""

    def __init__(self, services: ServiceManager):
        self.services = services
        self.window = None
        self.tray = None
        self.hotkey_listener = None
        self._expanded = False
        self._collapsed_pos: tuple[int, int] | None = None
        self._stopping = False  # set true on quit so the supervisor stops

    # -- JS API methods (callable from frontend as window.pywebview.api.*) --

    def expand(self) -> None:
        if not self.window:
            return
        try:
            self.window.resize(*EXPANDED_SIZE)
            self._expanded = True
        except Exception as e:
            log.warning(f"expand failed: {e}")

    def collapse(self) -> None:
        if not self.window:
            return
        try:
            self.window.resize(*COLLAPSED_SIZE)
            self._expanded = False
        except Exception as e:
            log.warning(f"collapse failed: {e}")

    def quit_app(self) -> None:
        log.info("Quit requested from UI")
        self._quit()

    # -- Self-healing supervisor --

    def _supervisor_loop(self) -> None:
        """While the orb is open, silently restart any engine that dies.

        Crash-loop guard: if the same engine needs 5 restarts within 2 minutes,
        stop trying and log loudly — restarting a genuinely-broken process
        forever helps nobody.
        """
        backend_restarts: list[float] = []
        frontend_restarts: list[float] = []
        backend_gave_up = False
        frontend_gave_up = False

        while not self._stopping:
            time.sleep(15)
            if self._stopping:
                break
            now = time.monotonic()

            # --- Backend ---
            if not backend_gave_up and not self.services.is_backend_alive():
                backend_restarts = [t for t in backend_restarts if now - t < 120]
                if len(backend_restarts) >= 5:
                    backend_gave_up = True
                    log.error("Backend crash-looping — supervisor giving up. "
                              "Check ~/.jarvis/logs/backend.log")
                else:
                    log.info("Backend down — restarting silently")
                    backend_restarts.append(now)
                    try:
                        self.services.ensure_backend()
                    except Exception as e:
                        log.warning(f"backend restart failed: {e}")

            # --- Frontend ---
            if not frontend_gave_up and not self.services.is_frontend_alive():
                frontend_restarts = [t for t in frontend_restarts if now - t < 120]
                if len(frontend_restarts) >= 5:
                    frontend_gave_up = True
                    log.error("Frontend crash-looping — supervisor giving up. "
                              "Check ~/.jarvis/logs/frontend.log")
                else:
                    log.info("Frontend down — restarting silently")
                    frontend_restarts.append(now)
                    try:
                        self.services.ensure_frontend()
                    except Exception as e:
                        log.warning(f"frontend restart failed: {e}")

    # -- Window control --

    def toggle_visible(self) -> None:
        if not self.window:
            return
        try:
            if getattr(self.window, "hidden", False):
                self.window.show()
            else:
                self.window.hide()
        except Exception as e:
            log.warning(f"toggle_visible failed: {e}")

    # -- Tray --

    def _start_tray(self) -> None:
        import pystray
        from pystray import MenuItem as Item, Menu

        icon_img = _build_tray_icon()

        def on_show(icon, item):
            self.window.show() if self.window else None

        def on_hide(icon, item):
            self.window.hide() if self.window else None

        def on_open_browser(icon, item):
            # Opens the full web UI in the user's default browser (no ?shell=1)
            import webbrowser
            webbrowser.open(FRONTEND_URL)

        def on_quit(icon, item):
            icon.stop()
            self._quit()

        self.tray = pystray.Icon(
            "jarvis",
            icon_img,
            "JARVIS",
            menu=Menu(
                Item("Show", on_show, default=True),
                Item("Hide", on_hide),
                Item("Open in browser", on_open_browser),
                Menu.SEPARATOR,
                Item("Quit", on_quit),
            ),
        )
        self.tray.run()

    # -- Global hotkey --

    def _start_hotkey(self) -> None:
        try:
            from pynput import keyboard
            self.hotkey_listener = keyboard.GlobalHotKeys({DEFAULT_HOTKEY: self.toggle_visible})
            self.hotkey_listener.start()
            log.info(f"Shell hotkey listening on {DEFAULT_HOTKEY}")
        except Exception as e:
            log.warning(f"Failed to register shell hotkey: {e}")

    # -- Lifecycle --

    def _quit(self) -> None:
        self._stopping = True  # stop the supervisor from restarting things
        try:
            if self.hotkey_listener:
                self.hotkey_listener.stop()
        except Exception:
            pass
        try:
            self.services.shutdown()
        except Exception as e:
            log.warning(f"service shutdown failed: {e}")
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass
        os._exit(0)

    def _on_closed(self) -> None:
        log.info("Window closed by user")
        self._quit()

    def _on_moved(self, x: int, y: int) -> None:
        # Persist only when collapsed (so the user's chosen "home corner" is what we restore)
        if not self._expanded:
            _save_window_state(x, y)

    def start(self) -> None:
        import webview

        state = _load_window_state()
        # Default to top-right corner — pywebview accepts None for "use defaults"
        x = state.get("x")
        y = state.get("y")

        # Append ?shell=1 so the frontend reliably enters shell mode at load
        # time (window.pywebview is injected too late for our detection).
        shell_url = FRONTEND_URL + ("&" if "?" in FRONTEND_URL else "?") + "shell=1"
        self.window = webview.create_window(
            "JARVIS",
            shell_url,
            width=COLLAPSED_SIZE[0],
            height=COLLAPSED_SIZE[1],
            x=x,
            y=y,
            frameless=True,
            on_top=True,
            transparent=True,
            easy_drag=True,
            background_color="#000000",
            resizable=False,
            js_api=self,
        )

        # Hook window events when they become available (pywebview calls these post-start)
        self.window.events.closed += self._on_closed
        try:
            self.window.events.moved += self._on_moved
        except Exception:
            pass

        # Tray, hotkey, and self-healing supervisor in background threads
        threading.Thread(target=self._start_tray, daemon=True).start()
        threading.Thread(target=self._start_hotkey, daemon=True).start()
        threading.Thread(target=self._supervisor_loop, daemon=True).start()

        # webview.start() blocks the main thread until the window closes
        webview.start(debug=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    log.info("JARVIS Desktop Shell starting")

    services = ServiceManager()
    services.ensure_backend()
    services.ensure_frontend()

    if not services.wait_ready():
        log.error("One or more services failed to start. Aborting.")
        services.shutdown()
        return 1

    shell = JarvisShell(services)
    try:
        shell.start()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    finally:
        services.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
