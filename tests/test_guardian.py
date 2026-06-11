"""Tests for Guardian Angel pattern matching, cooldown, and synthesis."""
import time
import types
import unittest
from unittest.mock import patch, MagicMock

import config


def _evt(source, content, age_s=5):
    return {"ts": time.time() - age_s, "source": source, "content": content}


class TestPatternMatching(unittest.TestCase):

    def setUp(self):
        config.GUARDIAN_THRESHOLD = 0.70

    def test_sensitive_paste_detected(self):
        from agent.guardian import match_patterns
        events = [_evt("clipboard", "Copied: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")]
        match = match_patterns(events)
        self.assertIsNotNone(match)
        self.assertEqual(match.kind, "sensitive_paste")

    def test_angry_email_detected(self):
        from agent.guardian import match_patterns
        events = [
            _evt("window", "Switched to: Gmail - Compose"),
            _evt("clipboard", "Copied: I find this completely unacceptable and your service is absolutely terrible, I demand a full refund immediately and expect"),
        ]
        match = match_patterns(events)
        self.assertIsNotNone(match)
        self.assertEqual(match.kind, "angry_message")

    def test_benign_clipboard_no_match(self):
        from agent.guardian import match_patterns
        events = [
            _evt("window", "Switched to: Gmail"),
            _evt("clipboard", "Copied: Hello, hope you are doing well"),
        ]
        match = match_patterns(events)
        self.assertIsNone(match)

    def test_destructive_commit_in_clipboard(self):
        from agent.guardian import match_patterns
        events = [
            _evt("window", "Switched to: Terminal"),
            _evt("clipboard", "Copied: git push --force origin main"),
        ]
        match = match_patterns(events)
        self.assertIsNotNone(match)
        self.assertEqual(match.kind, "destructive_commit")

    def test_shopping_cart_night_fires(self):
        from agent.guardian import match_patterns, _night_multiplier
        events = [_evt("window", "Switched to: Amazon - Cart checkout")]
        # Mock night time multiplier to be 2.0
        with patch("agent.guardian._night_multiplier", return_value=2.0):
            match = match_patterns(events)
        self.assertIsNotNone(match)
        self.assertIn(match.kind, ("night_purchase",))

    def test_stale_events_ignored(self):
        from agent.guardian import match_patterns
        # Events older than 30 seconds should be ignored
        events = [
            _evt("window", "Switched to: Gmail - Compose", age_s=35),
            _evt("clipboard", "Copied: This is absolutely terrible and unacceptable garbage", age_s=35),
        ]
        match = match_patterns(events)
        self.assertIsNone(match)

    def test_drop_table_detected(self):
        from agent.guardian import match_patterns
        events = [
            _evt("window", "Switched to: psql"),
            _evt("clipboard", "Copied: DROP TABLE users;"),
        ]
        match = match_patterns(events)
        self.assertIsNotNone(match)
        self.assertEqual(match.kind, "destructive_commit")


class TestCooldown(unittest.TestCase):

    def test_cooldown_suppresses_repeat(self):
        from agent.guardian import GuardianAngel
        ga = GuardianAngel(
            speak_fn=lambda x: None,
            tray_notify_fn=lambda t, m: None,
            recall_fn=lambda q, n: "",
        )
        config.GUARDIAN_COOLDOWN_MINUTES = 20
        # First fire should succeed
        self.assertTrue(ga._should_fire("angry_message"))
        # Immediate repeat should be blocked
        self.assertFalse(ga._should_fire("angry_message"))
        # Different kind should still fire
        self.assertTrue(ga._should_fire("sensitive_paste"))

    def test_cooldown_resets_after_expiry(self):
        from agent.guardian import GuardianAngel
        ga = GuardianAngel(
            speak_fn=lambda x: None,
            tray_notify_fn=lambda t, m: None,
            recall_fn=lambda q, n: "",
        )
        config.GUARDIAN_COOLDOWN_MINUTES = 0  # zero cooldown
        self.assertTrue(ga._should_fire("angry_message"))
        # With 0 cooldown, next fire is immediate
        self.assertTrue(ga._should_fire("angry_message"))


class TestSynthesiser(unittest.TestCase):

    def test_both_proceed_returns_none(self):
        from agent.guardian import GuardianAngel
        ga = GuardianAngel(lambda x: None, lambda t, m: None, lambda q, n: "")
        result = ga._synthesise(["PROCEED", "Proceed, this looks fine."])
        self.assertIsNone(result)

    def test_one_warning_returned(self):
        from agent.guardian import GuardianAngel
        ga = GuardianAngel(lambda x: None, lambda t, m: None, lambda q, n: "")
        result = ga._synthesise(["PROCEED", "Wait — that email sounds hostile, consider softening the tone."])
        self.assertIsNotNone(result)
        self.assertIn("email", result)

    def test_picks_longer_warning(self):
        from agent.guardian import GuardianAngel
        ga = GuardianAngel(lambda x: None, lambda t, m: None, lambda q, n: "")
        result = ga._synthesise([
            "That email sounds angry.",
            "Wait — that email sounds quite hostile and may damage the relationship; consider softening the tone before sending.",
        ])
        self.assertIn("hostile", result)

    def test_empty_responses_returns_none(self):
        from agent.guardian import GuardianAngel
        ga = GuardianAngel(lambda x: None, lambda t, m: None, lambda q, n: "")
        self.assertIsNone(ga._synthesise([]))


class TestRecentLog(unittest.TestCase):

    def test_log_stores_and_retrieves(self):
        from agent.guardian import GuardianAngel, MomentMatch
        delivered = []
        ga = GuardianAngel(
            speak_fn=lambda x: delivered.append(x),
            tray_notify_fn=lambda t, m: None,
            recall_fn=lambda q, n: "",
        )
        match = MomentMatch(
            kind="angry_message",
            description="drafting a heated email",
            query_hint="email",
            confidence=0.90,
        )
        ga._deliver(match, "That email sounds angry — sleep on it.")
        log = ga.recent_log(5)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["kind"], "angry_message")
        self.assertEqual(log[0]["verdict"], "That email sounds angry — sleep on it.")

    def test_log_capped_at_100(self):
        from agent.guardian import GuardianAngel, MomentMatch
        ga = GuardianAngel(lambda x: None, lambda t, m: None, lambda q, n: "")
        for i in range(120):
            match = MomentMatch("t", "d", "q", 0.9)
            ga._deliver(match, f"verdict {i}")
        self.assertLessEqual(len(ga._log), 100)


if __name__ == "__main__":
    unittest.main()
