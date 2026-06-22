"""
JARVIS Screen Awareness — see what's on the user's screen.

Cross-platform:
  Windows  — PIL.ImageGrab for screenshots, pygetwindow for window list
  macOS    — screencapture + AppleScript (original behaviour)
"""

import asyncio
import base64
import io
import logging
import sys
import tempfile
from pathlib import Path

import usage

log = logging.getLogger("jarvis.screen")


def _track(model: str, feature: str, response) -> None:
    """Best-effort: log token usage after a vision call."""
    try:
        in_t = getattr(response.usage, "input_tokens", 0)
        out_t = getattr(response.usage, "output_tokens", 0)
        usage.log_llm_call(feature=feature, model=model, input_tokens=in_t, output_tokens=out_t)
    except Exception:
        pass

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


# ---------------------------------------------------------------------------
# Window list
# ---------------------------------------------------------------------------

async def get_active_windows() -> list[dict]:
    """Get list of visible windows with app name, window title, and frontmost flag."""
    if IS_WINDOWS:
        return await _get_active_windows_windows()
    return await _get_active_windows_mac()


async def _get_active_windows_windows() -> list[dict]:
    """Enumerate visible windows on Windows via pygetwindow."""
    try:
        import pygetwindow as gw  # type: ignore
        import asyncio

        def _collect():
            results = []
            try:
                all_wins = gw.getAllWindows()
                active = gw.getActiveWindow()
                active_title = active.title if active else ""
                for w in all_wins:
                    if w.title and w.visible:
                        # Best-effort: use title as app name fallback
                        results.append({
                            "app": w.title.split(" - ")[-1] if " - " in w.title else w.title,
                            "title": w.title,
                            "frontmost": w.title == active_title,
                        })
            except Exception as e:
                log.warning(f"pygetwindow error: {e}")
            return results

        return await asyncio.get_event_loop().run_in_executor(None, _collect)
    except ImportError:
        log.warning("pygetwindow not installed — run: pip install pygetwindow")
        return []
    except Exception as e:
        log.warning(f"get_active_windows_windows error: {e}")
        return []


async def _get_active_windows_mac() -> list[dict]:
    """Enumerate visible windows on macOS via AppleScript."""
    script = """
set windowList to ""
tell application "System Events"
    set frontApp to name of first application process whose frontmost is true
    set visibleApps to every application process whose visible is true
    repeat with proc in visibleApps
        set appName to name of proc
        try
            set winCount to count of windows of proc
            if winCount > 0 then
                repeat with w in (windows of proc)
                    try
                        set winTitle to name of w
                        if winTitle is not "" and winTitle is not missing value then
                            set windowList to windowList & appName & "|||" & winTitle & "|||" & (appName = frontApp) & linefeed
                        end if
                    end try
                end repeat
            end if
        end try
    end repeat
end tell
return windowList
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode != 0:
            log.warning(f"get_active_windows failed: {stderr.decode()[:200]}")
            return []
        windows = []
        for line in stdout.decode().strip().split("\n"):
            parts = line.strip().split("|||")
            if len(parts) >= 3:
                windows.append({
                    "app": parts[0].strip(),
                    "title": parts[1].strip(),
                    "frontmost": parts[2].strip().lower() == "true",
                })
        return windows
    except asyncio.TimeoutError:
        log.warning("get_active_windows timed out")
        return []
    except Exception as e:
        log.warning(f"get_active_windows error: {e}")
        return []


async def get_running_apps() -> list[str]:
    """Get list of running application names (visible only)."""
    if IS_WINDOWS:
        try:
            import pygetwindow as gw  # type: ignore
            def _collect():
                return list({
                    w.title.split(" - ")[-1]
                    for w in gw.getAllWindows()
                    if w.title and w.visible
                })
            return await asyncio.get_event_loop().run_in_executor(None, _collect)
        except ImportError:
            return []
        except Exception as e:
            log.warning(f"get_running_apps error: {e}")
            return []

    # macOS
    script = """
tell application "System Events"
    set appNames to name of every application process whose visible is true
    set output to ""
    repeat with a in appNames
        set output to output & a & linefeed
    end repeat
    return output
end tell
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return [a.strip() for a in stdout.decode().strip().split("\n") if a.strip()]
        return []
    except Exception as e:
        log.warning(f"get_running_apps error: {e}")
        return []


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

async def take_screenshot(display_only: bool = True) -> str | None:
    """Take a screenshot and return base64-encoded PNG.

    Args:
        display_only: If True, capture main display only (macOS only).

    Returns:
        Base64-encoded PNG string, or None on failure.
    """
    if IS_WINDOWS:
        return await _screenshot_windows()
    return await _screenshot_mac(display_only)


async def _screenshot_windows() -> str | None:
    """Take a screenshot on Windows using PIL.ImageGrab."""
    try:
        from PIL import ImageGrab  # type: ignore

        def _grab() -> str:
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            log.info(f"Screenshot captured: {len(data)} bytes")
            return base64.b64encode(data).decode()

        return await asyncio.get_event_loop().run_in_executor(None, _grab)
    except ImportError:
        log.warning("Pillow not installed — run: pip install Pillow")
        return None
    except Exception as e:
        log.warning(f"Screenshot error: {e}")
        return None


async def _screenshot_mac(display_only: bool = True) -> str | None:
    """Take a screenshot on macOS using screencapture."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
    try:
        cmd = ["screencapture", "-x"]
        if display_only:
            cmd.append("-m")
        cmd.append(tmp_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0 or not Path(tmp_path).exists():
            log.warning("Screenshot capture failed")
            return None

        data = Path(tmp_path).read_bytes()
        log.info(f"Screenshot captured: {len(data)} bytes")
        return base64.b64encode(data).decode()
    except asyncio.TimeoutError:
        log.warning("Screenshot timed out")
        return None
    except Exception as e:
        log.warning(f"Screenshot error: {e}")
        return None
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Describe screen (vision)
# ---------------------------------------------------------------------------

async def describe_screen(anthropic_client) -> str:
    """Describe what's on the user's screen.

    Tries screenshot + vision first. Falls back to window list + LLM summary.
    """
    screenshot_b64 = await take_screenshot()
    if screenshot_b64 and anthropic_client:
        try:
            response = await anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=(
                    "You are JARVIS analyzing a screenshot of the user's desktop. "
                    "Describe what you see concisely: which apps are open, what the user "
                    "appears to be working on, any notable content visible. "
                    "Be specific about app names, file names, URLs, code, or documents visible. "
                    "2-4 sentences max. No markdown."
                ),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "What's on my screen right now?",
                        },
                    ],
                }],
            )
            _track("claude-haiku-4-5-20251001", "screen_vision_voice", response)
            return response.content[0].text
        except Exception as e:
            log.warning(f"Vision call failed, falling back to window list: {e}")

    # Fallback: window list
    windows = await get_active_windows()
    apps = await get_running_apps()

    if not windows and not apps:
        return "I wasn't able to see your screen, sir. Screen recording permission may be needed."

    context_parts = []
    if windows:
        for w in windows:
            marker = " (ACTIVE)" if w["frontmost"] else ""
            context_parts.append(f"{w['app']}: {w['title']}{marker}")

    if apps:
        window_apps = set(w["app"] for w in windows) if windows else set()
        bg_apps = [a for a in apps if a not in window_apps]
        if bg_apps:
            context_parts.append(f"Background apps: {', '.join(bg_apps)}")

    if anthropic_client and context_parts:
        try:
            response = await anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system=(
                    "You are JARVIS. Given the user's open windows and apps, summarize "
                    "what they appear to be working on in 1-2 sentences. Natural voice, no markdown."
                ),
                messages=[{"role": "user", "content": "Open windows:\n" + "\n".join(context_parts)}],
            )
            _track("claude-haiku-4-5-20251001", "screen_summary", response)
            return response.content[0].text
        except Exception:
            pass

    if windows:
        active = next((w for w in windows if w["frontmost"]), None)
        result = f"You have {len(windows)} windows open across {len(set(w['app'] for w in windows))} apps."
        if active:
            result += f" Currently focused on {active['app']}: {active['title']}."
        return result

    return f"Running apps: {', '.join(apps)}. Couldn't read window titles, sir."


async def describe_screen_for_coding(anthropic_client) -> str:
    """Describe the screen with a pair-programmer framing.

    Different system prompt from describe_screen(): looks for concrete problems
    (errors, bugs, typos, failing tests, broken UI) and names them specifically.
    Used by the global screen-vision hotkey.
    """
    screenshot_b64 = await take_screenshot()
    if not screenshot_b64 or not anthropic_client:
        return "I couldn't grab your screen, sir."

    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=(
                "You are JARVIS looking over the user's shoulder as they work. "
                "If you see a clear problem (error message, bug, typo, failing test, "
                "broken UI), name it specifically — include line numbers, variable "
                "names, or exact error text if visible. If the screen is fine, offer "
                "one dry observation about what they're doing. Max 2 sentences. "
                "British butler tone. No markdown."
            ),
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Take a look at my screen and tell me what you see.",
                    },
                ],
            }],
        )
        _track("claude-haiku-4-5-20251001", "screen_vision_hotkey", response)
        return response.content[0].text
    except Exception as e:
        log.warning(f"describe_screen_for_coding vision call failed: {e}")
        return "The vision model didn't cooperate, sir."


def format_windows_for_context(windows: list[dict]) -> str:
    """Format window list as context string for the LLM."""
    if not windows:
        return ""
    lines = ["Currently open on your desktop:"]
    for w in windows:
        marker = " (active)" if w["frontmost"] else ""
        lines.append(f"  - {w['app']}: {w['title']}{marker}")
    return "\n".join(lines)
