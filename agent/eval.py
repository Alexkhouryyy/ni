"""Session replay and structural evaluation harness.

Loads recorded user turns from turn_log, feeds them through the agent, and
scores the results structurally — no extra API calls needed for scoring.
Semantic quality still requires human judgment.

The replay function itself requires a live ANTHROPIC_API_KEY. Tests of the
scoring logic (score_turn, aggregate_score, load_session_turns) are fully
offline and live in tests/test_eval.py.

Quick start:
    from agent import eval as ev, core
    agent = core.AgentCore()
    result = ev.replay_session(42, agent)
    print(f"session {result.session_id}: score={result.score:.2f}")
    for t in result.turns:
        print(f"  Q: {t.user_text[:60]} | ok={t.replayed_ok} | {t.latency_ms}ms")
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

from agent import longterm


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """One replayed user turn and its structural outcome."""
    user_text: str
    original_response: str   # text from turn_log
    replayed_response: str   # text from new agent.run() call
    replayed_ok: bool        # completed without iteration-limit or API error
    latency_ms: int = 0


@dataclass
class ReplayResult:
    session_id: int
    turns: list[TurnResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return aggregate_score(self.turns)


# ---------------------------------------------------------------------------
# Data loading from turn_log
# ---------------------------------------------------------------------------

def load_session_turns(session_id: int) -> list[dict]:
    """Return paired (user, assistant) turns for a session from turn_log.

    Each entry is {"user": {..., "text": str}, "assistant": {"text": str, "tool_calls": list}}.
    Only pairs where a user message (role='user') is followed by at least one
    assistant message (role='assistant') are included. The LAST assistant message
    before the next user turn is used — it holds the final text response after
    any tool-use iterations.
    """
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id, ts, turn_index, role, content_json, tool_calls_json "
            "FROM turn_log WHERE session_id = ? ORDER BY ts",
            (session_id,),
        ).fetchall()

    pairs: list[dict] = []
    pending_user: Optional[dict] = None
    last_assistant: Optional[dict] = None

    for row in rows:
        role = row[3]
        try:
            content = json.loads(row[4] or "{}")
        except Exception:
            content = {}
        try:
            tool_calls = json.loads(row[5] or "[]")
        except Exception:
            tool_calls = []

        if role == "user":
            # Arriving at a new user turn — seal the previous segment
            if pending_user is not None and last_assistant is not None:
                pairs.append({"user": pending_user, "assistant": last_assistant})
            text = content.get("text", "") if isinstance(content, dict) else ""
            if text:
                pending_user = {
                    "id": row[0], "ts": row[1], "turn_index": row[2],
                    "text": text,
                }
                last_assistant = None
            else:
                pending_user = None
                last_assistant = None

        elif role == "assistant" and pending_user is not None:
            text = content.get("text", "") if isinstance(content, dict) else ""
            last_assistant = {"text": text, "tool_calls": tool_calls}

        # tool_result and error rows carry no data needed for replay — skip them

    # Seal the final segment
    if pending_user is not None and last_assistant is not None:
        pairs.append({"user": pending_user, "assistant": last_assistant})

    return pairs


def list_replayable_sessions(limit: int = 10) -> list[dict]:
    """Sessions that have recorded user turns, most recent first."""
    with longterm._conn() as c:
        rows = c.execute(
            """SELECT s.id, s.started_at, s.ended_at, s.summary,
                      COUNT(t.id) AS turn_count
               FROM sessions s
               JOIN turn_log t ON t.session_id = s.id AND t.role = 'user'
               GROUP BY s.id
               HAVING turn_count > 0
               ORDER BY s.started_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r[0], "started_at": r[1], "ended_at": r[2],
            "summary": (r[3] or "")[:200], "user_turn_count": r[4],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Scoring — structural only, no API required
# ---------------------------------------------------------------------------

_ERROR_MARKERS = (
    "rate-limited",
    "API error",
    "overloaded",
    "network issue",
    "server error",
    "API key was rejected",
    "I hit my iteration limit",
)


def score_turn(tr: TurnResult) -> float:
    """Structural score 0.0–1.0 for one replayed turn.

    Does NOT assess semantic quality; only checks completion and whether the
    response length is plausible relative to the original.

    0.0  — did not complete (API error, iteration limit, or empty response)
    0.6  — completed but length ratio is very different from original
    0.9  — completed with plausible length relative to original
    """
    if not tr.replayed_ok or not tr.replayed_response.strip():
        return 0.0
    orig_len = max(len(tr.original_response), 1)
    rep_len = len(tr.replayed_response)
    ratio = rep_len / orig_len
    # Allow a wide band — LLM responses vary. Only penalise extremes.
    return 0.9 if 0.15 <= ratio <= 8.0 else 0.6


def aggregate_score(turns: list[TurnResult]) -> float:
    """Mean score across all turns; 0.0 if the list is empty."""
    if not turns:
        return 0.0
    return sum(score_turn(t) for t in turns) / len(turns)


# ---------------------------------------------------------------------------
# Replay — requires live API (mark tests with @pytest.mark.integration)
# ---------------------------------------------------------------------------

def replay_session(
    session_id: int,
    agent,
    *,
    include_screenshot: bool = False,
) -> ReplayResult:
    """Replay every user turn in a recorded session through the given agent.

    Args:
        session_id:          session to replay from turn_log.
        agent:               AgentCore instance. Use a fresh instance so replay
                             history does not pollute the production conversation.
        include_screenshot:  whether to take a live screenshot per turn.

    Returns:
        ReplayResult with per-turn scores and any errors encountered.

    Note: does not suppress telemetry logging — pass an agent whose
    telemetry.log_turn is monkeypatched if you want a clean test run.
    """
    result = ReplayResult(session_id=session_id)
    pairs = load_session_turns(session_id)

    if not pairs:
        result.errors.append(f"No replayable turns found for session {session_id}.")
        return result

    for pair in pairs:
        user_text = pair["user"]["text"]
        original_response = pair["assistant"]["text"]

        t0 = time.perf_counter()
        try:
            replayed = agent.run(user_text, include_screenshot=include_screenshot)
        except Exception as e:
            ti = pair["user"]["turn_index"]
            result.errors.append(f"turn {ti}: agent.run raised {type(e).__name__}: {e}")
            replayed = ""

        latency_ms = int((time.perf_counter() - t0) * 1000)
        replayed_ok = bool(replayed) and not any(
            marker in replayed for marker in _ERROR_MARKERS
        )

        result.turns.append(TurnResult(
            user_text=user_text,
            original_response=original_response,
            replayed_response=replayed,
            replayed_ok=replayed_ok,
            latency_ms=latency_ms,
        ))

    return result
