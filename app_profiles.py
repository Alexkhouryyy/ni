"""
JARVIS App-Aware Behavior Profiles.

Maps the user's active foreground app to a small behavior profile (tone,
preferred actions, context hints). Injected into the system prompt as
{app_profile} so JARVIS shifts how he talks based on what you're doing —
technical in VSCode, editorial in Word, research-leaning in Chrome, etc.

Driven purely by the active-window data already collected by
screen.get_active_windows() — no extra polling, no extra cost.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Profile registry — order matters (first match wins)
# ---------------------------------------------------------------------------

APP_PROFILES: list[dict[str, Any]] = [
    {
        "match": r"\b(vscode|visual studio code|cursor|webstorm|pycharm|intellij|sublime text|atom|zed)\b|\bcode\.exe\b",
        "name": "Code Reviewer",
        "tone": "Technical and precise. Reference variables, functions, and files by name when you can see them on screen.",
        "preferred_actions": ["PROMPT_PROJECT", "SCREEN", "BUILD"],
        "context_hint": "When the user asks a vague question, they probably mean about the code currently on screen. Use [ACTION:SCREEN] if you need to look.",
    },
    {
        "match": r"\b(chrome|firefox|edge|safari|brave|arc|opera)\b",
        "name": "Research Assistant",
        "tone": "Curious and forward-leaning. Offer to summarize the page or pull related sources when relevant.",
        "preferred_actions": ["BROWSE", "LIVE_RESEARCH", "REMEMBER"],
        "context_hint": "If the user asks a factual question, the answer may live on the page in front of them. [ACTION:SCREEN] can confirm.",
    },
    {
        "match": r"\b(winword|microsoft word|word)\b|\.docx?\b",
        "name": "Editor",
        "tone": "Polished and editorial. Care about flow, word choice, structure, brevity. Avoid filler.",
        "preferred_actions": ["CREATE_NOTE", "ADD_NOTE"],
        "context_hint": "User may want phrasing suggestions, a draft, or to capture an idea as a note.",
    },
    {
        "match": r"\b(powerpoint|powerpnt|microsoft powerpoint)\b|\.pptx?\b",
        "name": "Presentation Coach",
        "tone": "Slide-aware. Think hierarchy, narrative arc, key message per slide. One idea per slide.",
        "preferred_actions": ["LIVE_RESEARCH"],
        "context_hint": "User is building a deck — favor clarity and structure over depth.",
    },
    {
        "match": r"\b(excel|microsoft excel)\b|\.xlsx?\b",
        "name": "Analyst",
        "tone": "Data-aware. Reference cells, columns, formulas when you can see them.",
        "preferred_actions": [],
        "context_hint": "User is in a spreadsheet — talk in tables, not paragraphs.",
    },
    {
        "match": r"\b(windowsterminal|cmd\.exe|powershell|pwsh|wt\.exe|iterm|warp|hyper|alacritty)\b|\bterminal\b",
        "name": "Ops Engineer",
        "tone": "Command-line precise. Prefer one-liners and exact paths. Skip the prose.",
        "preferred_actions": ["OPEN_TERMINAL", "PROMPT_PROJECT"],
        "context_hint": "User is at a shell — they want commands, not explanations.",
    },
    {
        "match": r"\b(spotify|youtube music|apple music|tidal)\b",
        "name": "Background DJ",
        "tone": "Light and conversational. The user is not in deep-work mode.",
        "preferred_actions": [],
        "context_hint": "Music is playing — keep things easy.",
    },
    {
        "match": r"\b(slack|discord|microsoft teams|whatsapp|telegram|signal|messenger)\b",
        "name": "Comms Triage",
        "tone": "Concise. Help them get through messages, not dwell.",
        "preferred_actions": ["REMEMBER", "ADD_TASK"],
        "context_hint": "User is on comms — surface action items, suggest follow-ups, capture commitments.",
    },
    {
        "match": r"\b(figma|sketch|adobe xd|photoshop|illustrator|affinity)\b",
        "name": "Design Partner",
        "tone": "Visual and craft-aware. Talk hierarchy, contrast, spacing, intent.",
        "preferred_actions": [],
        "context_hint": "User is designing — think in terms of users, intent, and visual language.",
    },
]

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "General",
    "tone": "Default JARVIS — composed butler, dry wit, economy of words.",
    "preferred_actions": [],
}


# ---------------------------------------------------------------------------
# Detection + formatting
# ---------------------------------------------------------------------------

def detect_active_profile(windows: list[dict]) -> dict[str, Any]:
    """Find the frontmost window and return the matching profile (or DEFAULT_PROFILE).

    `windows` is the list returned by screen.get_active_windows() — each entry has
    keys: app, title, frontmost.
    """
    if not windows:
        return DEFAULT_PROFILE
    active = next((w for w in windows if w.get("frontmost")), None)
    if not active:
        # Fall back to the first window if none flagged frontmost
        active = windows[0]
    haystack = f"{active.get('app','')} {active.get('title','')}".lower()
    for prof in APP_PROFILES:
        try:
            if re.search(prof["match"], haystack, re.IGNORECASE):
                return prof
        except re.error:
            continue
    return DEFAULT_PROFILE


def format_profile_for_prompt(profile: dict[str, Any]) -> str:
    """Render the profile as a short system-prompt block.

    Returns "" for the default profile so the prompt stays clean when no
    specific app is recognized.
    """
    if profile.get("name") == "General":
        return ""
    lines = [f"ACTIVE APP MODE: {profile['name']}", profile.get("tone", "")]
    if profile.get("context_hint"):
        lines.append(profile["context_hint"])
    actions = profile.get("preferred_actions") or []
    if actions:
        lines.append(f"Lean toward these actions when relevant: {', '.join(actions)}.")
    return "\n".join(line for line in lines if line)
