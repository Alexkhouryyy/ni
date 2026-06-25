"""Skill: work_mode — persistent Claude Code sessions per project directory.

Start a named working session that launches Claude Code (-p) in a project
directory. Subsequent messages continue the session via --continue.
Sessions are persisted to ~/Documents/Apex/work_sessions.json.

Trusted, hand-written skill. Requires 'claude' CLI on PATH.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

DESCRIPTION = (
    "Manage persistent Claude Code working sessions per project. "
    "Pass {action: 'start|send|status|stop', project_dir?, project_name?, message?}."
)
VERSION = "1.0"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["start", "send", "status", "stop"],
            "description": "start: open new session. send: continue session. status: list. stop: end session.",
        },
        "project_name": {
            "type": "string",
            "description": "Short name for the project, e.g. 'apex'. Identifies the session.",
            "default": "default",
        },
        "project_dir": {
            "type": "string",
            "description": "Absolute path to the project directory (required for 'start').",
        },
        "message": {
            "type": "string",
            "description": "Prompt/message to send to Claude Code (required for 'start' and 'send').",
        },
    },
    "required": ["action"],
}

_SESSIONS_FILE = Path.home() / "Documents" / "Apex" / "work_sessions.json"


def _load() -> dict:
    try:
        return json.loads(_SESSIONS_FILE.read_text()) if _SESSIONS_FILE.exists() else {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSIONS_FILE.write_text(json.dumps(data, indent=2))


def _run_claude(cwd: str, prompt: str, resume: bool) -> str:
    args = ["claude", "-p", prompt] + (["--continue"] if resume else [])
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0 and not out:
            return f"claude exited {result.returncode}: {err[:400]}"
        return out or "(no output)"
    except FileNotFoundError:
        return "work_mode: 'claude' not on PATH. Install Claude Code CLI first."
    except subprocess.TimeoutExpired:
        return "work_mode: claude timed out after 120s."
    except Exception as e:
        return f"work_mode: error: {e}"


def run(inputs: dict) -> str:
    action = inputs.get("action", "status")
    sessions = _load()
    name = inputs.get("project_name") or "default"

    if action == "status":
        if not sessions:
            return "No active work sessions."
        lines = [
            f"  {n}: {info.get('project_dir', '?')} (started {int((time.time()-info.get('started_at',0))/60)}m ago)"
            for n, info in sessions.items()
        ]
        return "Active sessions:\n" + "\n".join(lines)

    if action == "start":
        project_dir = inputs.get("project_dir", "")
        message = inputs.get("message") or "Hello. Review this project and tell me its current state."
        if not project_dir:
            return "work_mode: 'project_dir' is required to start a session."
        expanded = os.path.expanduser(project_dir)
        if not os.path.isdir(expanded):
            return f"work_mode: directory not found: {expanded}"
        sessions[name] = {"project_dir": expanded, "started_at": time.time()}
        _save(sessions)
        out = _run_claude(expanded, message, resume=False)
        return f"Started session '{name}' in {expanded}.\n\nClaude Code:\n{out}"

    if action == "send":
        message = inputs.get("message", "")
        if not message:
            return "work_mode: 'message' is required for 'send'."
        if name not in sessions:
            return f"work_mode: no session '{name}'. Use action='start' first."
        out = _run_claude(sessions[name].get("project_dir", "."), message, resume=True)
        return f"Claude Code ({name}):\n{out}"

    if action == "stop":
        if name in sessions:
            del sessions[name]
            _save(sessions)
            return f"Session '{name}' stopped."
        return f"No session named '{name}'."

    return f"work_mode: unknown action '{action}'."
