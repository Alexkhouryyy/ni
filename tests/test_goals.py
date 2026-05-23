"""Unit tests for agent/goals.py — strategic goal tracking and self-evaluation."""
import time
import types
import pytest

from agent import goals, longterm


@pytest.fixture(autouse=True)
def goals_db(test_db):
    goals.init_db()
    return test_db


# ── set_goal ───────────────────────────────────────────────────────────────

class TestSetGoal:
    def test_creates_active_goal(self):
        result = goals.set_goal("Launch beta", "ship the product", horizon="week")
        assert "Goal #" in result
        rows = goals.list_goals(active_only=True)
        assert any(g["title"] == "Launch beta" for g in rows)

    def test_returns_goal_id_in_message(self):
        result = goals.set_goal("Alpha", horizon="day")
        assert "#1" in result or "#" in result

    @pytest.mark.parametrize("horizon", ["day", "week", "month", "quarter"])
    def test_valid_horizons(self, horizon):
        result = goals.set_goal(f"Goal {horizon}", horizon=horizon)
        assert "Goal #" in result

    def test_invalid_horizon_rejected(self):
        result = goals.set_goal("Bad goal", horizon="year")
        assert "Invalid horizon" in result
        assert not goals.list_goals()

    def test_valid_deadline_iso(self):
        result = goals.set_goal("Deadline goal", deadline_iso="2099-12-31")
        assert "Goal #" in result
        g = goals.list_goals()[0]
        assert g["deadline"] is not None

    def test_invalid_deadline_rejected(self):
        result = goals.set_goal("Bad deadline", deadline_iso="not-a-date")
        assert "Invalid deadline" in result

    def test_goal_stored_with_correct_fields(self):
        goals.set_goal("My goal", description="some desc", horizon="month")
        g = goals.list_goals()[0]
        assert g["title"] == "My goal"
        assert g["description"] == "some desc"
        assert g["horizon"] == "month"
        assert g["status"] == "active"


# ── list_goals ─────────────────────────────────────────────────────────────

class TestListGoals:
    def test_empty_db(self):
        assert goals.list_goals() == []

    def test_active_only_default(self):
        goals.set_goal("Active", horizon="week")
        goals.set_goal("Done", horizon="week")
        goals.update_goal(2, status="done")
        rows = goals.list_goals(active_only=True)
        assert len(rows) == 1
        assert rows[0]["title"] == "Active"

    def test_active_only_false_returns_all(self):
        goals.set_goal("A", horizon="week")
        goals.set_goal("B", horizon="week")
        goals.update_goal(2, status="done")
        rows = goals.list_goals(active_only=False)
        assert len(rows) == 2

    def test_horizon_filter(self):
        goals.set_goal("Weekly", horizon="week")
        goals.set_goal("Monthly", horizon="month")
        rows = goals.list_goals(active_only=False, horizon="month")
        assert len(rows) == 1
        assert rows[0]["title"] == "Monthly"

    def test_recent_progress_attached(self):
        goals.set_goal("With progress", horizon="week")
        goals.update_goal(1, progress_note="halfway there", score=5)
        g = goals.list_goals()[0]
        assert len(g["recent_progress"]) == 1
        assert g["recent_progress"][0]["note"] == "halfway there"
        assert g["recent_progress"][0]["score"] == 5

    def test_recent_progress_capped_at_5(self):
        goals.set_goal("Many notes", horizon="week")
        for i in range(7):
            goals.update_goal(1, progress_note=f"note {i}")
        g = goals.list_goals()[0]
        assert len(g["recent_progress"]) == 5


# ── update_goal ────────────────────────────────────────────────────────────

class TestUpdateGoal:
    def test_update_status(self):
        goals.set_goal("Finish", horizon="day")
        result = goals.update_goal(1, status="done")
        assert "status -> done" in result
        rows = goals.list_goals(active_only=False)
        assert rows[0]["status"] == "done"

    def test_invalid_status_rejected(self):
        goals.set_goal("Target", horizon="day")
        result = goals.update_goal(1, status="cancelled")
        assert "Invalid status" in result

    def test_add_progress_note(self):
        goals.set_goal("Progress test", horizon="week")
        result = goals.update_goal(1, progress_note="Made progress")
        assert "progress note added" in result

    def test_progress_note_with_score(self):
        goals.set_goal("Scored", horizon="week")
        goals.update_goal(1, progress_note="Good work", score=8)
        g = goals.list_goals()[0]
        assert g["recent_progress"][0]["score"] == 8

    def test_no_args_returns_nothing_to_update(self):
        goals.set_goal("Stale", horizon="week")
        result = goals.update_goal(1)
        assert "Nothing to update" in result

    @pytest.mark.parametrize("status", ["active", "paused", "done", "abandoned"])
    def test_all_valid_statuses(self, status):
        goals.set_goal("Target", horizon="week")
        result = goals.update_goal(1, status=status)
        assert "Invalid" not in result


# ── active_goals_for_prompt ────────────────────────────────────────────────

class TestActiveGoalsForPrompt:
    def test_empty_returns_empty_string(self):
        assert goals.active_goals_for_prompt() == ""

    def test_contains_goal_title(self):
        goals.set_goal("Ship feature X", horizon="week")
        prompt = goals.active_goals_for_prompt()
        assert "Ship feature X" in prompt
        assert "[week]" in prompt

    def test_done_goals_excluded(self):
        goals.set_goal("Done task", horizon="day")
        goals.update_goal(1, status="done")
        prompt = goals.active_goals_for_prompt()
        assert "Done task" not in prompt

    def test_deadline_shown_when_set(self):
        goals.set_goal("Deadline goal", deadline_iso="2099-06-01", horizon="month")
        prompt = goals.active_goals_for_prompt()
        assert "2099" in prompt

    def test_capped_at_eight_goals(self):
        for i in range(12):
            goals.set_goal(f"Goal {i}", horizon="week")
        prompt = goals.active_goals_for_prompt()
        # Should only show 8 of the 12
        shown = prompt.count("[week]")
        assert shown <= 8


# ── evaluate_recent_work (mocked) ──────────────────────────────────────────

class TestEvaluateRecentWork:
    def _mock_client(self, monkeypatch, return_text: str = "All good."):
        """Patch telemetry.create to return a fake Claude response."""
        import agent.goals as goals_mod
        from agent import telemetry

        class _Block:
            type = "text"
            text = return_text

        class _Usage:
            input_tokens = 100
            output_tokens = 50
            cache_read_input_tokens = 0
            cache_creation_input_tokens = 0

        class _Resp:
            content = [_Block()]
            usage = _Usage()
            stop_reason = "end_turn"

        monkeypatch.setattr(telemetry, "create", lambda *a, **kw: _Resp())
        return object()  # fake client handle — not used directly

    def test_returns_string(self, monkeypatch):
        client = self._mock_client(monkeypatch)
        result = goals.evaluate_recent_work(client, days=1)
        assert isinstance(result, str)
        assert "All good." in result

    def test_persists_as_session_summary(self, monkeypatch):
        client = self._mock_client(monkeypatch, "Review text here")
        goals.evaluate_recent_work(client, days=1)
        with longterm._conn() as c:
            row = c.execute(
                "SELECT summary FROM sessions WHERE summary LIKE '%Weekly self-eval%'"
            ).fetchone()
        assert row is not None
        assert "Review text here" in row[0]
