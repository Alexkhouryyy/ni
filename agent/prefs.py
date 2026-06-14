"""User preference distillation — compresses thumbs-up/down history into a usable digest.

Runs as part of reflection.consolidate(). The digest is stored in the world_state
table under key 'user_prefs' and injected into the system prompt so every response
benefits from accumulated preference signals.
"""
import time
from typing import Optional

import config
from agent import longterm, telemetry

_PREFS_KEY = "user_prefs"
_DISTILL_INTERVAL = 7 * 86400  # only rebuild weekly


def _last_distill_ts() -> float:
    try:
        with longterm._conn() as c:
            row = c.execute(
                "SELECT updated_at FROM world_state WHERE key = ?", (_PREFS_KEY,)
            ).fetchone()
        return row[0] if row else 0.0
    except Exception:
        return 0.0


def get() -> str:
    """Return the current preference digest, or empty string if none yet."""
    try:
        with longterm._conn() as c:
            row = c.execute(
                "SELECT value FROM world_state WHERE key = ?", (_PREFS_KEY,)
            ).fetchone()
        return row[0] if row else ""
    except Exception:
        return ""


def distill(client, force: bool = False) -> str:
    """Distill thumbs-up/down feedback into a preference digest.

    Skips if called within _DISTILL_INTERVAL unless force=True.
    Stores result in world_state table. Returns the digest text.
    """
    now = time.time()
    if not force and now - _last_distill_ts() < _DISTILL_INTERVAL:
        return get()

    cutoff = now - 90 * 86400  # last 90 days of feedback
    try:
        with longterm._conn() as c:
            positives = c.execute(
                """SELECT tf.comment, tl.user_text, tl.assistant_text
                   FROM turn_feedback tf
                   LEFT JOIN turn_log tl
                     ON tl.session_id = tf.session_id AND tl.turn_index = tf.turn_index
                   WHERE tf.rating = 1 AND tf.ts >= ?
                   ORDER BY tf.ts DESC LIMIT 30""",
                (cutoff,),
            ).fetchall()
            negatives = c.execute(
                """SELECT tf.comment, tl.user_text, tl.assistant_text
                   FROM turn_feedback tf
                   LEFT JOIN turn_log tl
                     ON tl.session_id = tf.session_id AND tl.turn_index = tf.turn_index
                   WHERE tf.rating = -1 AND tf.ts >= ?
                   ORDER BY tf.ts DESC LIMIT 30""",
                (cutoff,),
            ).fetchall()
    except Exception as e:
        print(f"[Prefs] DB query failed: {e}")
        return get()

    if not positives and not negatives:
        return get()

    def _fmt(rows: list) -> str:
        lines = []
        for comment, user_text, asst_text in rows:
            parts = []
            if user_text:
                parts.append(f"Q: {str(user_text)[:100]}")
            if asst_text:
                parts.append(f"A: {str(asst_text)[:100]}")
            if comment:
                parts.append(f"Note: {comment}")
            if parts:
                lines.append(" | ".join(parts))
        return "\n".join(lines[:20]) or "(none)"

    prompt = (
        "You are an AI agent reviewing your own past performance to understand what the user likes.\n\n"
        f"POSITIVE FEEDBACK (thumbs up, {len(positives)} examples):\n{_fmt(positives)}\n\n"
        f"NEGATIVE FEEDBACK (thumbs down, {len(negatives)} examples):\n{_fmt(negatives)}\n\n"
        "Write a concise preference digest (max 250 words) with these sections:\n"
        "1. Communication style (length, tone, format)\n"
        "2. Content preferences (detail level, examples, caveats)\n"
        "3. What to avoid (patterns from thumbs down)\n"
        "4. Other clear patterns\n\n"
        "Be specific and actionable. Each point should change a concrete behavior."
    )

    try:
        resp = telemetry.create(
            client,
            call_site="agent.prefs/distill",
            model=config.PROACTIVE_MODEL,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        digest = resp.content[0].text.strip()
    except Exception as e:
        print(f"[Prefs] Distillation failed: {e}")
        return get()

    try:
        with longterm._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO world_state (key, value, updated_at) VALUES (?, ?, ?)",
                (_PREFS_KEY, digest, now),
            )
    except Exception as e:
        print(f"[Prefs] Failed to persist digest: {e}")

    return digest
