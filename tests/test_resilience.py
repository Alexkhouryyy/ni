"""Unit tests for agent/resilience.py — pure functions, no API calls."""
import httpx
import anthropic
import pytest
from agent import resilience


def _rate_limit():
    req = httpx.Request("POST", "https://api.anthropic.com")
    return anthropic.RateLimitError("rate limited", response=httpx.Response(429, request=req), body=None)


def _status(code: int):
    req = httpx.Request("POST", "https://api.anthropic.com")
    return anthropic.APIStatusError("err", response=httpx.Response(code, request=req), body=None)


def _conn():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


def _timeout():
    return anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com"))


class TestClassify:
    def test_rate_limit(self):
        assert resilience.classify(_rate_limit()) == "rate_limit"

    def test_overloaded_529(self):
        assert resilience.classify(_status(529)) == "overloaded"

    def test_server_error_500(self):
        assert resilience.classify(_status(500)) == "server_error"

    def test_server_error_503(self):
        assert resilience.classify(_status(503)) == "server_error"

    def test_auth_401(self):
        assert resilience.classify(_status(401)) == "auth"

    def test_auth_403(self):
        assert resilience.classify(_status(403)) == "auth"

    def test_client_error_400(self):
        assert resilience.classify(_status(400)) == "client_error"

    def test_client_error_422(self):
        assert resilience.classify(_status(422)) == "client_error"

    def test_network_connection(self):
        assert resilience.classify(_conn()) == "network"

    def test_network_timeout(self):
        assert resilience.classify(_timeout()) == "network"

    def test_non_api_exception(self):
        assert resilience.classify(ValueError("boom")) == "unexpected"

    def test_runtime_error(self):
        assert resilience.classify(RuntimeError("oops")) == "unexpected"


class TestFriendlyMessage:
    def test_all_known_categories_have_nonempty_message(self):
        for cat, msg in resilience._MESSAGES.items():
            assert isinstance(msg, str) and msg.strip(), f"empty message for {cat!r}"

    def test_rate_limit_message_mentions_limit_or_rate(self):
        msg = resilience.friendly_message(_rate_limit())
        assert any(kw in msg.lower() for kw in ("rate", "limit"))

    def test_network_message_mentions_network_or_reach(self):
        msg = resilience.friendly_message(_conn())
        assert any(kw in msg.lower() for kw in ("network", "reach", "api"))

    def test_overloaded_message_mentions_overloaded_or_try(self):
        msg = resilience.friendly_message(_status(529))
        assert any(kw in msg.lower() for kw in ("overload", "try"))

    def test_unknown_exception_returns_fallback(self):
        msg = resilience.friendly_message(KeyboardInterrupt())
        assert isinstance(msg, str) and msg.strip()
