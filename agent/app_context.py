"""App-aware context profiles — shifts agent tone to match the foreground app.

Detects the active window title and returns a short system-prompt injection that
re-roles the agent (e.g. VSCode → Code Reviewer, Slack → Comms Triage).

Detection: pygetwindow on Windows, xdotool on Linux/macOS. Degrades silently to
None if neither is available. Activated when APP_CONTEXT_ENABLED=true (default).
"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional

_PROFILES: list[dict] = [
    {
        "matches": ["visual studio code", "vscode", "code - "],
        "name": "Code Reviewer",
        "role": "Senior software engineer / code reviewer",
        "tone": "Precise, direct. Name functions. Spot bugs. Suggest refactors. Cut fluff.",
        "focus": "Code quality, correctness, performance, security.",
    },
    {
        "matches": ["chrome", "firefox", "edge", "safari"],
        "name": "Research Assistant",
        "role": "Expert researcher and analyst",
        "tone": "Cite sources. Distinguish facts from inference. Flag uncertainty.",
        "focus": "Information quality, cross-referencing, synthesis.",
    },
    {
        "matches": ["microsoft word", "google docs", "notion", "obsidian"],
        "name": "Writing Editor",
        "role": "Sharp-eyed writing editor",
        "tone": "Economy of language. Fix structure and flow. Cut redundancy.",
        "focus": "Clarity, concision, argument structure.",
    },
    {
        "matches": ["terminal", "powershell", "cmd.exe", "bash", "zsh", "iterm", " - wt"],
        "name": "Ops Engineer",
        "role": "Senior DevOps / SRE engineer",
        "tone": "Commands first, explain after. Flag destructive ops clearly.",
        "focus": "Reliability, automation, observability.",
    },
    {
        "matches": ["slack", "microsoft teams", "discord", "telegram"],
        "name": "Comms Triage",
        "role": "Strategic communications adviser",
        "tone": "Brief and actionable. Detect urgency. Surface what needs a reply.",
        "focus": "Priority, context, appropriate response framing.",
    },
    {
        "matches": ["figma", "sketch", "adobe xd"],
        "name": "Design Partner",
        "role": "Product designer and design system expert",
        "tone": "Visual-first. Speak in components, flows, hierarchy.",
        "focus": "UX consistency, accessibility, design system coherence.",
    },
    {
        "matches": ["spotify", "apple music", "youtube music"],
        "name": "Background DJ",
        "role": "Music curator",
        "tone": "Relaxed, minimal interruption. Suggest, don't insist.",
        "focus": "Ambience matching task and mood.",
    },
    {
        "matches": ["powerpoint", "keynote", "google slides"],
        "name": "Presentation Coach",
        "role": "Executive presentation coach",
        "tone": "One idea per slide. Strong headlines. Executive-audience framing.",
        "focus": "Clarity, slide economy, visual storytelling.",
    },
    {
        "matches": ["excel", "google sheets", "numbers", "tableau"],
        "name": "Data Analyst",
        "role": "Senior data analyst",
        "tone": "Numbers-first. Define metrics precisely. Flag data quality issues.",
        "focus": "Statistical rigour, chart choice, actionable insights.",
    },
]


def _get_active_window_title() -> Optional[str]:
    try:
        if sys.platform == "win32":
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else None
        else:
            r = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout.strip() or None
    except Exception:
        return None


def detect_active_profile() -> Optional[dict]:
    """Return the best matching profile dict, or None if no match."""
    title = _get_active_window_title()
    if not title:
        return None
    tl = title.lower()
    for p in _PROFILES:
        if any(m in tl for m in p["matches"]):
            return p
    return None


def format_profile_for_prompt(profile: dict) -> str:
    return (
        f"## ACTIVE CONTEXT — {profile['name']}\n"
        f"Role shift: {profile['role']}.\n"
        f"Tone: {profile['tone']}\n"
        f"Focus: {profile['focus']}"
    )


def get_context_block() -> Optional[str]:
    """Full pipeline: detect → format → return block string or None."""
    try:
        import config
        if not getattr(config, "APP_CONTEXT_ENABLED", True):
            return None
        profile = detect_active_profile()
        return format_profile_for_prompt(profile) if profile else None
    except Exception:
        return None
