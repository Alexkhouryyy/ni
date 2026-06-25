"""Skill: control_pc — terminal, browser, and app control for the host machine.

Opens terminals, launches browsers/apps, and spawns persistent Claude Code
sessions per project. Pure subprocess — no extra dependencies required.

Trusted, hand-written skill.
"""
from __future__ import annotations

import os
import subprocess
import sys

DESCRIPTION = (
    "Control the host PC: open a terminal, launch a browser or app, or start a "
    "persistent Claude Code session in a project directory. "
    "Pass {action, command?, url?, browser?, app_name?, project_dir?, prompt?}."
)
VERSION = "1.0"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["open_terminal", "open_browser", "launch_app", "spawn_claude_code"],
            "description": "Action to perform.",
        },
        "command": {
            "type": "string",
            "description": "Shell command to run in the new terminal (open_terminal).",
            "default": "",
        },
        "url": {
            "type": "string",
            "description": "URL to open (open_browser).",
        },
        "browser": {
            "type": "string",
            "description": "Browser executable, e.g. 'chrome', 'firefox'. Defaults to system default.",
            "default": "",
        },
        "app_name": {
            "type": "string",
            "description": "Application name or executable (launch_app).",
        },
        "project_dir": {
            "type": "string",
            "description": "Project directory path (spawn_claude_code).",
        },
        "prompt": {
            "type": "string",
            "description": "Initial prompt for the Claude Code session (spawn_claude_code).",
            "default": "",
        },
    },
    "required": ["action"],
}

_PLATFORM = sys.platform


def _open_terminal(command: str) -> str:
    cmd = command.strip()
    if _PLATFORM == "win32":
        if cmd:
            candidates = [["wt", "cmd", "/k", cmd], ["cmd", "/c", "start", "cmd", "/k", cmd]]
        else:
            candidates = [["wt"], ["cmd", "/c", "start"]]
    elif _PLATFORM == "darwin":
        script = f'tell application "Terminal" to do script "{cmd}"' if cmd else 'tell application "Terminal" to activate'
        candidates = [["osascript", "-e", script]]
    else:
        if cmd:
            candidates = [
                ["gnome-terminal", "--", "bash", "-c", cmd + "; exec bash"],
                ["xterm", "-e", cmd],
                ["konsole", "-e", cmd],
            ]
        else:
            candidates = [["gnome-terminal"], ["xterm"], ["konsole"]]

    for args in candidates:
        try:
            subprocess.Popen(args)
            return f"Opened terminal{f' running: {cmd}' if cmd else ''}."
        except FileNotFoundError:
            continue
        except Exception as e:
            return f"Terminal launch error: {e}"
    return "No terminal emulator found. Install wt / gnome-terminal / xterm and retry."


def _open_browser(url: str, browser: str) -> str:
    if not url:
        return "control_pc: 'url' is required for open_browser."
    if browser:
        try:
            subprocess.Popen([browser.strip(), url])
            return f"Opened {url} in {browser}."
        except FileNotFoundError:
            pass
    try:
        import webbrowser
        webbrowser.open(url)
        return f"Opened {url} in the system default browser."
    except Exception as e:
        return f"Browser launch failed: {e}"


def _launch_app(app_name: str) -> str:
    if not app_name:
        return "control_pc: 'app_name' is required for launch_app."
    try:
        if _PLATFORM == "win32":
            subprocess.Popen(["start", app_name], shell=True)
        elif _PLATFORM == "darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])
        return f"Launched {app_name}."
    except Exception as e:
        return f"App launch failed for '{app_name}': {e}"


def _spawn_claude_code(project_dir: str, prompt: str) -> str:
    if not project_dir:
        return "control_pc: 'project_dir' is required for spawn_claude_code."
    expanded = os.path.expanduser(project_dir)
    if not os.path.isdir(expanded):
        return f"control_pc: directory not found: {expanded}"
    try:
        args = ["claude", "-p", prompt] if prompt.strip() else ["claude"]
        proc = subprocess.Popen(args, cwd=expanded)
        return f"Spawned Claude Code session in {expanded} (pid {proc.pid})."
    except FileNotFoundError:
        return "control_pc: 'claude' not on PATH. Install the Claude Code CLI and retry."
    except Exception as e:
        return f"Claude Code spawn failed: {e}"


def run(inputs: dict) -> str:
    action = inputs.get("action", "")
    if action == "open_terminal":
        return _open_terminal(inputs.get("command", ""))
    if action == "open_browser":
        return _open_browser(inputs.get("url", ""), inputs.get("browser", ""))
    if action == "launch_app":
        return _launch_app(inputs.get("app_name", ""))
    if action == "spawn_claude_code":
        return _spawn_claude_code(inputs.get("project_dir", ""), inputs.get("prompt", ""))
    return (
        f"control_pc: unknown action '{action}'. "
        "Valid: open_terminal, open_browser, launch_app, spawn_claude_code."
    )
