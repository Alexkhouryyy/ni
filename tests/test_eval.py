"""Unit tests for agent/eval.py — no API required.

Covers scoring logic with constructed TurnResult objects, and data-loading
functions against a temporary in-memory DB (via the test_db fixture).
"""
import json
import time
import pytest

from agent.eval import (
    TurnResult, ReplayResult,
    score_turn, aggregate_score,
    load_session_turns, list_replayable_sessions,
    _ERROR_MARKERS,
)
from agent import longterm


def _turn(*, orig: str, replay: str, ok: bool = True) -> TurnResult:
    return TurnResult(
        user_text="test question",
        original_response=orig,
        replayed_response=replay,
        replayed_ok=ok,
    )


class TestScoreTurn:
    def test_not_ok_scores_zero(self):
        t = _turn(orig="some response", replay="something", ok=False)
        assert score_turn(t) == 0.0

    def test_empty_replay_scores_zero(self):
        t = _turn(orig="some response", replay="")
        assert score_turn(t) == 0.0

    def test_whitespace_only_replay_scores_zero(self):
        t = _turn(orig="some response", replay="   \n  ")
        assert score_turn(t) == 0.0

    def test_similar_length_scores_high(self):
        t = _turn(orig="This is a medium length answer.", replay="This is also a medium length answer.")
        assert score_turn(t) >= 0.9

    def test_very_short_replay_penalised(self):
        t = _turn(orig="A" * 500, replay="short", ok=True)
        # ratio ≈ 0.01, below 0.15 threshold
        assert score_turn(t) == 0.6

    def test_very_long_replay_penalised(self):
        t = _turn(orig="hi", replay="X" * 10000, ok=True)
        # ratio > 8.0 threshold
        assert score_turn(t) == 0.6

    def test_boundary_ratio_just_inside(self):
        orig = "A" * 100
        replay = "A" * 20   # ratio = 0.2, just above 0.15
        t = _turn(orig=orig, replay=replay)
        assert score_turn(t) == 0.9

    def test_score_is_float_between_0_and_1(self):
        for ok in (True, False):
            t = _turn(orig="hello", replay="world", ok=ok)
            s = score_turn(t)
            assert 0.0 <= s <= 1.0


class TestAggregateScore:
    def test_empty_list_returns_zero(self):
        assert aggregate_score([]) == 0.0

    def test_single_good_turn(self):
        t = _turn(orig="hello", replay="world")
        assert aggregate_score([t]) > 0.0

    def test_single_failed_turn(self):
        t = _turn(orig="hello", replay="", ok=False)
        assert aggregate_score([t]) == 0.0

    def test_mixed_turns_average(self):
        good = _turn(orig="hello", replay="world")
        bad = _turn(orig="hello", replay="", ok=False)
        s = aggregate_score([good, bad])
        assert 0.0 < s < score_turn(good)

    def test_all_ok_turns_score_above_zero(self):
        turns = [_turn(orig="x" * 50, replay="y" * 50) for _ in range(5)]
        assert aggregate_score(turns) > 0.0

    def test_replay_result_score_property(self):
        r = ReplayResult(session_id=99)
        r.turns.append(_turn(orig="hello", replay="world"))
        assert r.score == aggregate_score(r.turns)


class TestErrorMarkers:
    """Replays containing error-marker strings should be flagged as not ok."""

    @pytest.mark.parametrize("marker", _ERROR_MARKERS)
    def test_marker_in_replay_detected_in_ok_check(self, marker):
        # simulate what replay_session does: replayed_ok depends on absence of markers
        replayed = f"Some text. {marker} More text."
        replayed_ok = bool(replayed) and not any(m in replayed for m in _ERROR_MARKERS)
        assert not replayed_ok


class TestLoadSessionTurns:
    def test_empty_db_returns_empty_list(self, test_db):
        pairs = load_session_turns(999)
        assert pairs == []

    def test_returns_pairs_for_recorded_session(self, test_db):
        now = time.time()
        with longterm._conn() as c:
            c.execute(
                "INSERT INTO sessions (id, started_at) VALUES (?, ?)", (1, now)
            )
            # user turn
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, 1, 1, "user", json.dumps({"text": "What is 2+2?"}), "[]"),
            )
            # assistant turn (end_turn response)
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now + 1, 1, 1, "assistant", json.dumps({"text": "It is 4."}), "[]"),
            )

        pairs = load_session_turns(1)
        assert len(pairs) == 1
        assert pairs[0]["user"]["text"] == "What is 2+2?"
        assert pairs[0]["assistant"]["text"] == "It is 4."

    def test_last_assistant_response_used_after_tool_use(self, test_db):
        """When there are multiple assistant turns (tool-use loop), the last is used."""
        now = time.time()
        with longterm._conn() as c:
            c.execute("INSERT INTO sessions (id, started_at) VALUES (?, ?)", (2, now))
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, 2, 1, "user", json.dumps({"text": "Search for X"}), "[]"),
            )
            # first assistant (tool call, no text)
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now + 1, 2, 1, "assistant",
                 json.dumps({"text": ""}),
                 json.dumps([{"name": "web_search", "id": "x1"}])),
            )
            # tool result
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now + 2, 2, 1, "tool_result", json.dumps({"tool": "web_search", "preview": "..."}), "[]"),
            )
            # final assistant response
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now + 3, 2, 1, "assistant", json.dumps({"text": "Here are the results."}), "[]"),
            )

        pairs = load_session_turns(2)
        assert len(pairs) == 1
        assert pairs[0]["assistant"]["text"] == "Here are the results."

    def test_skips_user_turns_without_text(self, test_db):
        """Image-only user turns (no 'text' key) are not included."""
        now = time.time()
        with longterm._conn() as c:
            c.execute("INSERT INTO sessions (id, started_at) VALUES (?, ?)", (3, now))
            # user turn with no text (image-only)
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, 3, 1, "user", json.dumps({}), "[]"),
            )
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now + 1, 3, 1, "assistant", json.dumps({"text": "I see an image."}), "[]"),
            )

        pairs = load_session_turns(3)
        assert pairs == []


class TestListReplayableSessions:
    def test_empty_db_returns_empty(self, test_db):
        sessions = list_replayable_sessions()
        assert sessions == []

    def test_returns_sessions_with_user_turns(self, test_db):
        now = time.time()
        with longterm._conn() as c:
            c.execute("INSERT INTO sessions (id, started_at, summary) VALUES (?, ?, ?)", (10, now, "test session"))
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json, tool_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, 10, 1, "user", json.dumps({"text": "hello"}), "[]"),
            )

        sessions = list_replayable_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == 10
        assert sessions[0]["user_turn_count"] == 1
