"""Unit tests for agent/memory.py — in-memory, no API required."""
import pytest
from agent.memory import Memory, _SUMMARY_THRESHOLD


class TestAddAndRetrieve:
    def test_add_user_str_normalises_to_list(self):
        m = Memory()
        m.add_user("hello")
        msgs = m.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == [{"type": "text", "text": "hello"}]

    def test_add_user_list_stored_verbatim(self):
        m = Memory()
        block = {"type": "text", "text": "hi"}
        m.add_user([block])
        assert m.get_messages()[0]["content"] == [block]

    def test_add_assistant(self):
        m = Memory()
        m.add_assistant([{"type": "text", "text": "hey"}])
        msgs = m.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"

    def test_alternating_roles_preserved(self):
        m = Memory()
        m.add_user("q1")
        m.add_assistant([{"type": "text", "text": "a1"}])
        m.add_user("q2")
        roles = [msg["role"] for msg in m.get_messages()]
        assert roles == ["user", "assistant", "user"]

    def test_get_messages_returns_same_list(self):
        m = Memory()
        m.add_user("x")
        assert m.get_messages() is m.messages


class TestContextPrefix:
    def test_empty_when_no_summary(self):
        m = Memory()
        assert m.context_prefix() == ""

    def test_contains_summary(self):
        m = Memory()
        m.summary = "discussed project goals"
        prefix = m.context_prefix()
        assert "discussed project goals" in prefix

    def test_prefix_is_string(self):
        m = Memory()
        m.summary = "some summary"
        assert isinstance(m.context_prefix(), str)


class TestMaybeSummarize:
    def test_no_op_under_threshold(self):
        m = Memory()
        for i in range(_SUMMARY_THRESHOLD - 1):
            m.add_user(f"msg {i}")
        original_count = len(m.get_messages())
        m.maybe_summarize(None)  # client never called — threshold not reached
        assert len(m.get_messages()) == original_count
        assert m.summary == ""

    def test_no_op_exactly_at_threshold_minus_one(self):
        m = Memory()
        for i in range(_SUMMARY_THRESHOLD - 1):
            m.add_user(f"x")
        m.maybe_summarize(None)
        assert len(m.get_messages()) == _SUMMARY_THRESHOLD - 1

    def test_skips_gracefully_on_api_error(self, monkeypatch):
        """When the summarization API call fails, history is preserved intact."""
        import anthropic, httpx
        from agent import telemetry

        def boom(*a, **k):
            raise anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com")
            )

        monkeypatch.setattr(telemetry, "create", boom)

        m = Memory()
        for i in range(_SUMMARY_THRESHOLD):
            m.add_user(f"msg {i}")
        original_count = len(m.get_messages())

        m.maybe_summarize(object())  # triggers the threshold, API fails
        # history is preserved — not truncated
        assert len(m.get_messages()) == original_count
        assert m.summary == ""
