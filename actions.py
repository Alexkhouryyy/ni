"""
JARVIS Action Executor — cross-platform system actions.

Execute actions IMMEDIATELY, before generating any LLM response.
Each function returns {"success": bool, "confirmation": str}.
"""

import asyncio
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger("jarvis.actions")

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

DESKTOP_PATH = Path.home() / "Desktop"


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------

async def open_terminal(command: str = "") -> dict:
    """Open a terminal and optionally run a command."""
    if IS_WINDOWS:
        return await _open_terminal_windows(command)
    return await _open_terminal_mac(command)


async def _open_terminal_windows(command: str = "") -> dict:
    """Open Windows Terminal (or cmd as fallback) and run a command."""
    try:
        if command:
            # Try Windows Terminal first, fall back to cmd
            try:
                subprocess.Popen(
                    ["wt", "cmd", "/k", command],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            except FileNotFoundError:
                subprocess.Popen(
                    ["cmd", "/k", command],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
        else:
            try:
                subprocess.Popen(["wt"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            except FileNotFoundError:
                subprocess.Popen(["cmd"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return {"success": True, "confirmation": "Terminal is open, sir."}
    except Exception as e:
        log.error(f"open_terminal_windows failed: {e}")
        return {"success": False, "confirmation": "I had trouble opening the terminal, sir."}


async def _open_terminal_mac(command: str = "") -> dict:
    """Open Terminal.app on macOS via AppleScript."""
    if command:
        escaped = command.replace('"', '\\"')
        script = (
            'tell application "Terminal"\n'
            "    activate\n"
            f'    do script "{escaped}"\n'
            "end tell"
        )
    else:
        script = (
            'tell application "Terminal"\n'
            "    activate\n"
            "end tell"
        )
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_terminal_mac failed: {stderr.decode()}")
    else:
        await _mark_terminal_as_jarvis()
    return {
        "success": success,
        "confirmation": "Terminal is open, sir." if success else "I had trouble opening Terminal, sir.",
    }


async def _mark_terminal_as_jarvis(revert_after: float = 5.0):
    """macOS only — temporarily set Terminal to Ocean theme."""
    if not IS_MAC:
        return
    script_save = (
        'tell application "Terminal"\n'
        '    return name of current settings of front window\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_save,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        original_profile = stdout.decode().strip()

        script_set = (
            'tell application "Terminal"\n'
            '    set current settings of front window to settings set "Ocean"\n'
            'end tell'
        )
        proc2 = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_set,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        if original_profile and original_profile != "Ocean":
            asyncio.get_event_loop().call_later(
                revert_after,
                lambda: asyncio.ensure_future(_revert_terminal_theme(original_profile))
            )
    except Exception:
        pass


async def _revert_terminal_theme(profile_name: str):
    """macOS only — revert Terminal window back to its original profile."""
    if not IS_MAC:
        return
    escaped = profile_name.replace('"', '\\"')
    script = (
        'tell application "Terminal"\n'
        f'    set current settings of front window to settings set "{escaped}"\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

async def open_browser(url: str, browser: str = "chrome") -> dict:
    """Open URL in the user's browser (Chrome or Firefox)."""
    if IS_WINDOWS:
        return await _open_browser_windows(url, browser)
    return await _open_browser_mac(url, browser)


async def _open_browser_windows(url: str, browser: str = "chrome") -> dict:
    """Open a URL on Windows using the default browser or a specific one."""
    try:
        if browser.lower() == "firefox":
            try:
                subprocess.Popen(["firefox", url])
                app_name = "Firefox"
            except FileNotFoundError:
                # Fall back to default browser
                os.startfile(url)
                app_name = "your browser"
        else:
            # Try Chrome first, fall back to default browser
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            launched = False
            for path in chrome_paths:
                if Path(path).exists():
                    subprocess.Popen([path, url])
                    launched = True
                    break
            if not launched:
                os.startfile(url)
            app_name = "Chrome" if launched else "your browser"

        return {"success": True, "confirmation": f"Pulled that up in {app_name}, sir."}
    except Exception as e:
        log.error(f"open_browser_windows failed: {e}")
        return {"success": False, "confirmation": "Had trouble opening that in the browser, sir."}


async def _open_browser_mac(url: str, browser: str = "chrome") -> dict:
    """Open a URL on macOS via AppleScript."""
    escaped_url = url.replace('"', '\\"')
    if browser.lower() == "firefox":
        app_name = "Firefox"
        script = (
            'tell application "Firefox"\n'
            "    activate\n"
            f'    open location "{escaped_url}"\n'
            "end tell"
        )
    else:
        app_name = "Chrome"
        script = (
            'tell application "Google Chrome"\n'
            "    activate\n"
            f'    open location "{escaped_url}"\n'
            "end tell"
        )
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_browser_mac ({app_name}) failed: {stderr.decode()}")
    return {
        "success": success,
        "confirmation": f"Pulled that up in {app_name}, sir." if success else f"{app_name} ran into a problem, sir.",
    }


# Keep backward compat
async def open_chrome(url: str) -> dict:
    return await open_browser(url, "chrome")


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

async def open_claude_in_project(project_dir: str, prompt: str) -> dict:
    """Open a terminal, cd to project dir, run Claude Code interactively."""
    claude_md = Path(project_dir) / "CLAUDE.md"
    claude_md.write_text(f"# Task\n\n{prompt}\n\nBuild this completely. If web app, make index.html work standalone.\n")

    if IS_WINDOWS:
        return await _open_claude_windows(project_dir)
    return await _open_claude_mac(project_dir)


async def _open_claude_windows(project_dir: str) -> dict:
    """Launch Claude Code in a new terminal window on Windows."""
    try:
        cmd = f'cd /d "{project_dir}" && claude --dangerously-skip-permissions'
        try:
            subprocess.Popen(
                ["wt", "cmd", "/k", cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except FileNotFoundError:
            subprocess.Popen(
                ["cmd", "/k", cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        return {
            "success": True,
            "confirmation": "Claude Code is running in Terminal, sir. You can watch the progress.",
        }
    except Exception as e:
        log.error(f"open_claude_windows failed: {e}")
        return {"success": False, "confirmation": "Had trouble spawning Claude Code, sir."}


async def _open_claude_mac(project_dir: str) -> dict:
    """Launch Claude Code in Terminal.app on macOS."""
    script = (
        'tell application "Terminal"\n'
        "    activate\n"
        f'    do script "cd {project_dir} && claude --dangerously-skip-permissions"\n'
        "end tell"
    )
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_claude_mac failed: {stderr.decode()}")
    else:
        await _mark_terminal_as_jarvis()
    return {
        "success": success,
        "confirmation": "Claude Code is running in Terminal, sir. You can watch the progress."
        if success
        else "Had trouble spawning Claude Code, sir.",
    }


async def prompt_existing_terminal(project_name: str, prompt: str) -> dict:
    """Find a terminal window matching a project name and type a prompt into it."""
    if IS_WINDOWS:
        # On Windows we can't easily inject keystrokes into another terminal;
        # fall back to opening a new one in the right directory.
        log.warning("prompt_existing_terminal: Windows keystroke injection not supported, opening new terminal.")
        return {"success": False, "confirmation": f"Couldn't reach an existing terminal for {project_name} on Windows, sir. Opening a new one."}

    # macOS: original AppleScript behaviour
    escaped_name = project_name.replace('"', '\\"')
    escaped_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Terminal"
    set matched to false
    set targetWindow to missing value
    repeat with w in windows
        if name of w contains "{escaped_name}" then
            set targetWindow to w
            set matched to true
            exit repeat
        end if
    end repeat

    if not matched then
        return "NOT_FOUND"
    end if

    set index of targetWindow to 1
    set selected tab of targetWindow to selected tab of targetWindow
    activate
end tell

delay 1

tell application "System Events"
    tell process "Terminal"
        set frontmost to true
        delay 0.3
        keystroke "{escaped_prompt}"
        delay 0.2
        keystroke return
    end tell
end tell

return "OK"
'''
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        result = stdout.decode().strip()
        if result == "NOT_FOUND":
            return {"success": False, "confirmation": f"Couldn't find a terminal for {project_name}, sir."}
        success = proc.returncode == 0
        if not success:
            log.error(f"prompt_existing_terminal failed: {stderr.decode()[:200]}")
        if success:
            await _mark_terminal_as_jarvis()
        return {
            "success": success,
            "confirmation": f"Sent that to {project_name}, sir." if success
            else f"Had trouble typing into {project_name}, sir.",
        }
    except asyncio.TimeoutError:
        return {"success": False, "confirmation": "Terminal operation timed out, sir."}
    except Exception as e:
        log.error(f"prompt_existing_terminal failed: {e}")
        return {"success": False, "confirmation": "Something went wrong reaching that terminal, sir."}


# ---------------------------------------------------------------------------
# Chrome tab info
# ---------------------------------------------------------------------------

async def get_chrome_tab_info() -> dict:
    """Read the current Chrome tab's title and URL."""
    if IS_WINDOWS:
        return await _get_chrome_tab_windows()
    return await _get_chrome_tab_mac()


async def _get_chrome_tab_windows() -> dict:
    """Read current Chrome tab on Windows via pygetwindow title heuristic."""
    try:
        import pygetwindow as gw  # type: ignore
        def _find():
            for w in gw.getAllWindows():
                if "Google Chrome" in w.title and w.visible:
                    title = w.title.replace(" - Google Chrome", "").strip()
                    return {"title": title, "url": ""}
            return {}
        return await asyncio.get_event_loop().run_in_executor(None, _find)
    except ImportError:
        return {}
    except Exception as e:
        log.warning(f"get_chrome_tab_windows failed: {e}")
        return {}


async def _get_chrome_tab_mac() -> dict:
    """Read current Chrome tab on macOS via AppleScript."""
    script = (
        'tell application "Google Chrome"\n'
        "    set tabTitle to title of active tab of front window\n"
        "    set tabURL to URL of active tab of front window\n"
        '    return tabTitle & "|" & tabURL\n'
        "end tell"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            result = stdout.decode().strip()
            parts = result.split("|", 1)
            if len(parts) == 2:
                return {"title": parts[0], "url": parts[1]}
        return {}
    except Exception as e:
        log.warning(f"get_chrome_tab_mac failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Build monitor
# ---------------------------------------------------------------------------

async def monitor_build(project_dir: str, ws=None, synthesize_fn=None) -> None:
    """Monitor a Claude Code build for completion. Notify via WebSocket when done."""
    import base64

    output_file = Path(project_dir) / ".jarvis_output.txt"
    start = time.time()
    timeout = 600  # 10 minutes

    while time.time() - start < timeout:
        await asyncio.sleep(5)
        if output_file.exists():
            content = output_file.read_text()
            if "--- JARVIS TASK COMPLETE ---" in content:
                log.info(f"Build complete in {project_dir}")
                if ws and synthesize_fn:
                    try:
                        msg = "The build is complete, sir."
                        audio_bytes = await synthesize_fn(msg)
                        if audio_bytes:
                            encoded = base64.b64encode(audio_bytes).decode()
                            await ws.send_json({"type": "status", "state": "speaking"})
                            await ws.send_json({"type": "audio", "data": encoded, "text": msg})
                            await ws.send_json({"type": "status", "state": "idle"})
                    except Exception as e:
                        log.warning(f"Build notification failed: {e}")
                return

    log.warning(f"Build timed out in {project_dir}")


# ---------------------------------------------------------------------------
# Intent router
# ---------------------------------------------------------------------------

async def execute_action(intent: dict, projects: list = None) -> dict:
    """Route a classified intent to the right action function."""
    action = intent.get("action", "chat")
    target = intent.get("target", "")

    if action == "open_terminal":
        result = await open_terminal("claude --dangerously-skip-permissions")
        result["project_dir"] = None
        return result

    elif action == "browse":
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        else:
            url = f"https://www.google.com/search?q={quote(target)}"

        browser = "firefox" if "firefox" in target.lower() else "chrome"
        result = await open_browser(url, browser)
        result["project_dir"] = None
        return result

    elif action == "build":
        project_name = _generate_project_name(target)
        project_dir = str(DESKTOP_PATH / project_name)
        os.makedirs(project_dir, exist_ok=True)
        result = await open_claude_in_project(project_dir, target)
        result["project_dir"] = project_dir
        return result

    elif action == "order_food":
        return await execute_order_food(intent)

    elif action == "reserve_table":
        return await execute_reserve_table(intent)

    elif action == "order_status":
        return await execute_order_status()

    elif action == "cancel_order":
        return await execute_cancel_order(intent)

    else:
        return {"success": False, "confirmation": "", "project_dir": None}


# ---------------------------------------------------------------------------
# Order & Reservation action executors
# ---------------------------------------------------------------------------

async def execute_order_food(intent: dict) -> dict:
    """Start an order flow from an [ACTION:ORDER_FOOD] tag.

    The server handles the orchestrator state machine directly — this function
    is a lightweight shim used when execute_action() is called from outside
    the main WS handler (e.g. a REST endpoint test).
    """
    params = intent.get("params", {})
    raw = intent.get("target", "")
    return {
        "success": True,
        "confirmation": "Starting order flow, sir.",
        "project_dir": None,
        "order_params": params,
        "raw_request": raw,
    }


async def execute_reserve_table(intent: dict) -> dict:
    """Start a reservation flow from an [ACTION:RESERVE_TABLE] tag."""
    params = intent.get("params", {})
    return {
        "success": True,
        "confirmation": "Starting reservation flow, sir.",
        "project_dir": None,
        "reservation_params": params,
    }


async def execute_order_status() -> dict:
    """Return the current in-flight order status."""
    import memory as _mem
    active = _mem.get_active_order()
    if active:
        eta = active.get("eta_minutes")
        eta_str = f"ETA {eta} minutes" if eta else "ETA unknown"
        msg = f"{active['restaurant']} order is {active['status']}. {eta_str}."
    else:
        recent = _mem.recent_orders(1)
        if recent:
            o = recent[0]
            msg = f"Last order was {o['restaurant']}, status: {o['status']}."
        else:
            msg = "No recent orders on record, sir."
    return {"success": True, "confirmation": msg, "project_dir": None}


async def execute_cancel_order(intent: dict) -> dict:
    """Cancel a pending order."""
    from orders import order_orchestrator
    params = intent.get("params", {})
    oid_str = params.get("order_id", "")
    order_id = None
    if oid_str:
        try:
            order_id = int(oid_str)
        except ValueError:
            pass
    if order_id:
        msg = order_orchestrator.cancel_pending(order_id)
    else:
        msg = "No active order to cancel, sir."
    return {"success": True, "confirmation": msg, "project_dir": None}


def _generate_project_name(prompt: str) -> str:
    """Generate a kebab-case project folder name from the prompt."""
    quoted = re.search(r'"([^"]+)"', prompt)
    if quoted:
        name = quoted.group(1).strip()
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip()
        if name:
            return re.sub(r"[\s]+", "-", name.lower())

    called = re.search(r'(?:called|named)\s+(\S+(?:[-_]\S+)*)', prompt, re.IGNORECASE)
    if called:
        name = re.sub(r"[^a-zA-Z0-9-]", "", called.group(1))
        if len(name) > 3:
            return name.lower()

    words = re.sub(r"[^a-zA-Z0-9\s]", "", prompt.lower()).split()
    skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and",
            "to", "of", "i", "want", "need", "new", "project", "directory", "called",
            "on", "desktop", "that", "application", "app", "full", "stack", "simple",
            "web", "page", "site", "named"}
    meaningful = [w for w in words if w not in skip and len(w) > 2][:4]
    return "-".join(meaningful) if meaningful else "jarvis-project"
