"""Skill: email_triage — read the inbox and triage it with AI.

Fetches recent inbox messages, then asks Claude to classify each by urgency and
category, summarize it in one line, and (for messages that warrant a reply)
propose a short draft. Drafts are NOT sent — the agent stages them for approval
via the email_draft tool / dashboard.

Trusted, hand-written skill.
"""
from __future__ import annotations

import json

DESCRIPTION = (
    "Read and triage the email inbox: classify each message by urgency/category, "
    "summarize it, and suggest reply drafts. Pass {limit, unread_only}. "
    "Drafts are never sent automatically — they stage for your approval."
)
VERSION = "1.0"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "description": "How many recent messages to triage.", "default": 12},
        "unread_only": {"type": "boolean", "description": "Only triage unread messages.", "default": True},
    },
    "required": [],
}

_TRIAGE_PROMPT = """You are an executive assistant triaging an email inbox. For each message \
below, output a JSON array. Each element:
  {"uid": "<uid>", "urgency": "high|medium|low", "category": "action|reply|fyi|newsletter|spam",
   "summary": "<one concise line>", "needs_reply": true|false,
   "draft": "<short reply draft IF needs_reply, else empty>"}

Be decisive. "high" urgency = time-sensitive or from an important sender. Keep drafts brief and \
professional. Output ONLY the JSON array.

Messages:
{messages}"""


def run(inputs: dict) -> str:
    from tools import email_box
    if not email_box.is_configured():
        return ("Email isn't configured yet. Add EMAIL_ADDRESS and EMAIL_PASSWORD "
                "(an app-specific password) to your .env, then restart Apex.")

    limit = int(inputs.get("limit", 12))
    unread_only = bool(inputs.get("unread_only", True))
    msgs = email_box.fetch_inbox(limit=limit, unread_only=unread_only)
    if msgs and msgs[0].get("error"):
        return f"Could not read inbox: {msgs[0]['error']}"
    if not msgs:
        return "Inbox is clear — no messages to triage." + (" (unread only)" if unread_only else "")

    # Build a compact digest for the model.
    lines = []
    for m in msgs:
        lines.append(f"[uid={m['uid']}] From: {m['from']} | Subject: {m['subject']} | {m['date']}")
    digest = "\n".join(lines)

    try:
        import config
        import anthropic
        from agent import telemetry
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = telemetry.create(
            client,
            call_site="skills.email_triage/triage",
            model=config.AGENT_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": _TRIAGE_PROMPT.format(messages=digest)}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        s, e = text.find("["), text.rfind("]") + 1
        triaged = json.loads(text[s:e]) if s >= 0 and e > s else []
    except Exception as e:
        return f"Triage failed: {e}"

    if not triaged:
        return f"Read {len(msgs)} messages but couldn't structure the triage."

    order = {"high": 0, "medium": 1, "low": 2}
    triaged.sort(key=lambda t: order.get(t.get("urgency"), 3))
    out = [f"Triaged {len(triaged)} message(s):\n"]
    for t in triaged:
        flag = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(t.get("urgency"), "⚪")
        out.append(f"{flag} [{t.get('category', '?')}] {t.get('summary', '')}")
        if t.get("needs_reply") and t.get("draft"):
            out.append(f"    ↳ suggested reply (uid {t.get('uid')}): {t['draft'][:200]}")
    out.append("\nTo send any reply, ask me to draft it — I'll stage it for your approval, never send unprompted.")
    return "\n".join(out)
