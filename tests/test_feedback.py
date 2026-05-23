"""Unit tests for agent/feedback.py — user feedback on completed turns."""
import pytest

from agent import feedback


@pytest.fixture
def fb_db(test_db):
    """Reuse the shared test_db fixture but also init the feedback table."""
    feedback.init_db()
    return test_db


class TestRecord:
    def test_thumbs_up_round_trip(self, fb_db):
        row = feedback.record(1, session_id=1, turn_index=3, source="cli")
        assert row["rating"] == 1
        assert row["session_id"] == 1
        assert row["turn_index"] == 3
        assert row["source"] == "cli"

    def test_thumbs_down_with_comment(self, fb_db):
        row = feedback.record(-1, session_id=2, turn_index=1, comment="bad", source="dashboard")
        assert row["rating"] == -1
        assert row["comment"] == "bad"

    def test_invalid_rating_rejected(self, fb_db):
        with pytest.raises(ValueError):
            feedback.record(0, session_id=1, turn_index=1)
        with pytest.raises(ValueError):
            feedback.record(2, session_id=1, turn_index=1)

    def test_unknown_source_normalized(self, fb_db):
        row = feedback.record(1, session_id=1, turn_index=1, source="banana")
        assert row["source"] == "api"

    def test_upsert_overwrites_rating(self, fb_db):
        feedback.record(1, session_id=1, turn_index=1, source="cli")
        feedback.record(-1, session_id=1, turn_index=1, comment="changed mind", source="cli")
        row = feedback.for_turn(1, 1)
        assert row["rating"] == -1
        assert row["comment"] == "changed mind"


class TestQuery:
    def test_for_turn_missing(self, fb_db):
        assert feedback.for_turn(99, 99) is None

    def test_for_session_ordered(self, fb_db):
        feedback.record(1, session_id=5, turn_index=2)
        feedback.record(-1, session_id=5, turn_index=1)
        rows = feedback.for_session(5)
        assert [r["turn_index"] for r in rows] == [1, 2]

    def test_recent_ordered_desc(self, fb_db):
        feedback.record(1, session_id=1, turn_index=1)
        feedback.record(-1, session_id=2, turn_index=1)
        rows = feedback.recent(limit=10, days=1)
        assert len(rows) == 2
        assert rows[0]["session_id"] == 2  # most recent first


class TestSummary:
    def test_empty(self, fb_db):
        s = feedback.summary(days=7)
        assert s["thumbs_up"] == 0
        assert s["thumbs_down"] == 0
        assert s["total"] == 0
        assert s["approval_rate"] is None

    def test_ratio(self, fb_db):
        feedback.record(1, session_id=1, turn_index=1)
        feedback.record(1, session_id=1, turn_index=2)
        feedback.record(1, session_id=1, turn_index=3)
        feedback.record(-1, session_id=1, turn_index=4)
        s = feedback.summary(days=7)
        assert s["thumbs_up"] == 3
        assert s["thumbs_down"] == 1
        assert s["total"] == 4
        assert s["approval_rate"] == 0.75

    def test_by_source(self, fb_db):
        feedback.record(1, session_id=1, turn_index=1, source="cli")
        feedback.record(-1, session_id=1, turn_index=2, source="dashboard")
        s = feedback.summary(days=7)
        by_src = {r["source"]: r for r in s["by_source"]}
        assert by_src["cli"]["thumbs_up"] == 1
        assert by_src["dashboard"]["thumbs_down"] == 1


class TestPhraseDetection:
    @pytest.mark.parametrize("text", [
        "thumbs up", "Thumbs Up.", "good job!", "that was helpful",
        "perfect", "exactly right",
    ])
    def test_positive_phrases(self, text):
        assert feedback.detect_feedback_phrase(text) == 1

    @pytest.mark.parametrize("text", [
        "thumbs down", "bad answer", "that was wrong", "not helpful",
        "that didn't work",
    ])
    def test_negative_phrases(self, text):
        assert feedback.detect_feedback_phrase(text) == -1

    @pytest.mark.parametrize("text", [
        "hello", "what time is it", "search the web for cats",
        "", "    ",
    ])
    def test_neutral_text(self, text):
        assert feedback.detect_feedback_phrase(text) is None

    def test_long_message_not_treated_as_feedback(self):
        # A long sentence containing "thumbs up" is a real query, not pure feedback.
        text = "thumbs up but also can you go ahead and find me the latest news on AI agents please"
        assert feedback.detect_feedback_phrase(text) is None
