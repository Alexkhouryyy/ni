"""Tests for agent/outcomes.py — outcome tracking correlated with feedback."""
import time
import pytest

from agent import longterm, feedback, outcomes


@pytest.fixture
def outcomes_db(test_db, monkeypatch):
    """Isolated DB with all required tables."""
    feedback.init_db()
    # Ensure skill_usage has the new columns (migration should run in init_db)
    return test_db


def _insert_session(session_id: int, started_at: float = None):
    t = started_at or time.time()
    with longterm._conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
            (session_id, t),
        )


def _insert_turn_log(session_id: int, turn_index: int, ts: float, role: str = "user"):
    with longterm._conn() as c:
        c.execute(
            "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, session_id, turn_index, role, '{"text": "hi"}'),
        )


def _insert_skill_usage(name: str, success: bool, ts: float, session_id=None, turn_index=None):
    with longterm._conn() as c:
        c.execute(
            "INSERT INTO skill_usage (ts, name, success, duration, session_id, turn_index) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, name, 1 if success else 0, 0.1, session_id, turn_index),
        )


def _insert_reflection(status: str, ts: float, kind: str = "pattern", confidence: float = 0.9):
    with longterm._conn() as c:
        c.execute(
            "INSERT INTO reflections (ts, kind, content, confidence, status, action_json) "
            "VALUES (?, ?, ?, ?, ?, '{}')",
            (ts, kind, "test reflection", confidence, status),
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestSkillOutcomes:
    def test_empty(self, outcomes_db):
        assert outcomes.skill_outcomes() == []

    def test_unrated_runs_counted_but_no_approval(self, outcomes_db):
        now = time.time()
        _insert_skill_usage("searcher", True, now, session_id=1, turn_index=1)
        rows = outcomes.skill_outcomes(days=1)
        assert len(rows) == 1
        assert rows[0]["name"] == "searcher"
        assert rows[0]["total_runs"] == 1
        assert rows[0]["rated_runs"] == 0
        assert rows[0]["approval_rate"] is None

    def test_rated_run_computes_approval(self, outcomes_db):
        now = time.time()
        _insert_skill_usage("searcher", True, now, session_id=1, turn_index=1)
        feedback.record(1, session_id=1, turn_index=1)
        rows = outcomes.skill_outcomes(days=1)
        assert rows[0]["rated_runs"] == 1
        assert rows[0]["thumbs_up"] == 1
        assert rows[0]["approval_rate"] == 1.0

    def test_mixed_feedback(self, outcomes_db):
        now = time.time()
        for i in range(4):
            _insert_skill_usage("summarize", True, now - i, session_id=1, turn_index=i + 1)
            feedback.record(
                1 if i < 3 else -1,
                session_id=1, turn_index=i + 1,
            )
        rows = outcomes.skill_outcomes(days=1)
        r = rows[0]
        assert r["thumbs_up"] == 3
        assert r["thumbs_down"] == 1
        assert r["approval_rate"] == 0.75

    def test_name_filter(self, outcomes_db):
        now = time.time()
        _insert_skill_usage("alpha", True, now, session_id=1, turn_index=1)
        _insert_skill_usage("beta", True, now, session_id=1, turn_index=2)
        rows = outcomes.skill_outcomes(name="alpha", days=1)
        assert len(rows) == 1
        assert rows[0]["name"] == "alpha"

    def test_days_filter_excludes_old(self, outcomes_db):
        old = time.time() - 10 * 86400  # 10 days ago
        _insert_skill_usage("oldskill", True, old, session_id=1, turn_index=1)
        rows = outcomes.skill_outcomes(days=7)
        assert rows == []

    def test_multiple_runs_same_turn_counted_correctly(self, outcomes_db):
        """Two skill runs in the same (session, turn) → one feedback row; approval_rate stays 1.0."""
        now = time.time()
        _insert_skill_usage("doer", True, now, session_id=1, turn_index=1)
        _insert_skill_usage("doer", True, now, session_id=1, turn_index=1)
        feedback.record(1, session_id=1, turn_index=1)
        rows = outcomes.skill_outcomes(days=1)
        r = rows[0]
        assert r["total_runs"] == 2
        # feedback can only match once per (session, turn) → rated_runs=1 per run but feedback is unique
        # The LEFT JOIN produces 2 rows (one per skill_usage), both joined to the same feedback row
        assert r["rated_runs"] == 2
        assert r["thumbs_up"] == 2
        assert r["approval_rate"] == 1.0


class TestReflectionOutcomes:
    def test_empty(self, outcomes_db):
        assert outcomes.reflection_outcomes() == []

    def test_pending_reflection_not_included(self, outcomes_db):
        _insert_reflection("pending", time.time())
        assert outcomes.reflection_outcomes() == []

    def test_applied_reflection_with_no_turns(self, outcomes_db):
        _insert_reflection("applied", time.time())
        rows = outcomes.reflection_outcomes(days=7, window_hours=24)
        assert len(rows) == 1
        r = rows[0]
        assert r["pre_turns"] == 0
        assert r["post_turns"] == 0
        assert r["delta"] is None

    def test_applied_reflection_with_pre_and_post_turns(self, outcomes_db):
        refl_ts = time.time()
        _insert_reflection("applied", refl_ts)

        # 3 pre-turns: 2 thumbs-up, 1 thumbs-down
        for i in range(3):
            t = refl_ts - (i + 1) * 3600  # 1-3h before reflection
            _insert_turn_log(session_id=10, turn_index=i + 1, ts=t)
            feedback.record(1 if i < 2 else -1, session_id=10, turn_index=i + 1)

        # 4 post-turns: all thumbs-up
        for i in range(4):
            t = refl_ts + (i + 1) * 3600  # 1-4h after reflection
            _insert_turn_log(session_id=10, turn_index=i + 10, ts=t)
            feedback.record(1, session_id=10, turn_index=i + 10)

        rows = outcomes.reflection_outcomes(days=7, window_hours=48)
        assert len(rows) == 1
        r = rows[0]
        assert r["pre_turns"] == 3
        assert r["pre_rate"] == pytest.approx(2 / 3, rel=1e-3)
        assert r["post_turns"] == 4
        assert r["post_rate"] == 1.0
        assert r["delta"] == pytest.approx(1.0 - 2 / 3, abs=1e-2)

    def test_window_excludes_turns_outside_range(self, outcomes_db):
        refl_ts = time.time()
        _insert_reflection("applied", refl_ts)

        # Turn that's 10 days before the reflection (outside default 7d window)
        far_ts = refl_ts - 10 * 86400
        _insert_turn_log(session_id=20, turn_index=1, ts=far_ts)
        feedback.record(1, session_id=20, turn_index=1)

        rows = outcomes.reflection_outcomes(days=7, window_hours=24)
        r = rows[0]
        assert r["pre_turns"] == 0  # outside the 24h window


class TestOverall:
    def test_empty_returns_defaults(self, outcomes_db):
        r = outcomes.overall(days=7)
        assert r["approval_rate"] is None
        assert r["total_rated_turns"] == 0
        assert r["worst_skills"] == []
        assert r["best_skills"] == []
        assert r["applied_reflections_in_window"] == 0

    def test_with_data(self, outcomes_db):
        now = time.time()
        # Two skill runs, one rated positive, one negative
        _insert_skill_usage("alpha", True, now, session_id=1, turn_index=1)
        _insert_skill_usage("alpha", True, now, session_id=1, turn_index=2)
        _insert_skill_usage("alpha", True, now, session_id=1, turn_index=3)
        feedback.record(1, session_id=1, turn_index=1)
        feedback.record(1, session_id=1, turn_index=2)
        feedback.record(1, session_id=1, turn_index=3)

        _insert_skill_usage("beta", True, now, session_id=1, turn_index=4)
        _insert_skill_usage("beta", True, now, session_id=1, turn_index=5)
        _insert_skill_usage("beta", True, now, session_id=1, turn_index=6)
        feedback.record(-1, session_id=1, turn_index=4)
        feedback.record(-1, session_id=1, turn_index=5)
        feedback.record(-1, session_id=1, turn_index=6)

        r = outcomes.overall(days=1)
        assert r["total_skills_run"] == 2
        assert r["total_rated_turns"] == 6
        # worst_skills needs rated_runs >= 3
        assert len(r["worst_skills"]) >= 1
        assert r["worst_skills"][0]["name"] == "beta"
