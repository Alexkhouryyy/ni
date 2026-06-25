"""Screen vision tool — screenshot + Claude Haiku vision analysis.

Provides two operations:
  take_screenshot() -> base64 JPEG string or None
  describe_screen(mode) -> natural-language description via Haiku vision

Modes:
  general  — what's on screen, what the user is doing
  coding   — pair-programmer mode: find errors, suggest improvements
  context  — brief one-line summary for injection into other prompts

Capture: PIL.ImageGrab (Windows/macOS) then mss (cross-platform fallback).
"""
from __future__ import annotations

import base64
import io
from typing import Optional

_MODE_PROMPTS: dict[str, str] = {
    "general": (
        "You are a sharp AI assistant watching the user's screen. "
        "Describe what's on screen in 2–3 sentences: app, content, and what the user appears to be doing. "
        "Be specific — name the app, file, or website."
    ),
    "coding": (
        "You are a senior software engineer doing pair programming via screen share. "
        "Look at this screenshot and identify: (1) any visible errors or warnings, "
        "(2) the code being worked on and its apparent purpose, "
        "(3) one concrete improvement or suggestion. Be direct and brief."
    ),
    "context": (
        "Give a one-line context summary of what is currently on screen. "
        "Format: '<App>: <what the user is doing>'. "
        "Example: 'VSCode: editing auth middleware in Python'."
    ),
}


def take_screenshot() -> Optional[str]:
    """Return the current screen as a base64 JPEG string, or None on failure."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=75)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass

    try:
        import mss
        import mss.tools
        from PIL import Image
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[0])
            buf = io.BytesIO(mss.tools.to_png(raw.rgb, raw.size))
            img = Image.open(buf).convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=75)
            return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return None


def describe_screen(mode: str = "general") -> str:
    """Capture screen and describe it via Claude Haiku vision."""
    b64 = take_screenshot()
    if b64 is None:
        return "[screen_vision] Could not capture screen. PIL.ImageGrab or mss required."

    prompt = _MODE_PROMPTS.get(mode, _MODE_PROMPTS["general"])
    try:
        import config
        import anthropic
        from agent import telemetry
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = telemetry.create(
            client,
            call_site="tools.screen_vision/describe",
            model=config.PROACTIVE_MODEL,
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"[screen_vision] Vision call failed: {e}"
