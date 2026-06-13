"""Tests for Time Capsule: pre-filter, extraction parsing, capture, surface, throttle."""
import time
import unittest

import config
from agent import longterm


def _mk_tc():
    from agent.timecapsule import TimeCapsule
    spoken, toasted = [], []
    tc = TimeCapsule(
        speak_fn=lambda x: spoken.append(x),
        tray_notify_fn=lambda t, m: toasted.append((t, m)),
    )
    return tc, spoken, toasted


# ── Pure functions (no DB) ───────────────────────────────────────────────────

class TestPrefilter(unittest.TestCase):
    def test_goal_phrase_fires(self):
        from agent.timecapsule import _PREFILTER
        self.assertTrue(_PREFILTER.search("I want to start running every morning"))
        self.assertTrue(_PREFILTER.search("I'm going to quit my job by March"))
        self.assertTrue(_PREFILTER.search("my goal is to read more books"))

    def test_emotion_phrase_fires(self):
        from agent.timecapsule import _PREFILTER
        self.assertTrue(_PREFILTER.search("I'm so done with this place"))
        self.assertTrue(_PREFILTER.search("honestly I can't take this anymore"))

    def test_chitchat_silent(self):
        from agent.timecapsule import _PREFILTER
        self.assertIsNone(_PREFILTER.search("what's the weather like today?"))
        self.assertIsNone(_PREFILTER.search("can you summarize this file for me"))
        self.assertIsNone(_PREFILTER.search("thanks, that worked"))


class TestExtractionParse(unittest.TestCase):
    def setUp(self):
        config.TIME_CAPSULE_DEFAULT_CALLBACK_DAYS = 14

    def test_valid_json(self):
        from agent.timecapsule import _coerce_extraction
        out = _coerce_extraction(
            '{"capture": true, "kind": "goal", "statement": "start running", "callback_days": 7}'
        )
        self.assertEqual(out, {"statement": "start running", "kind": "goal", "callback_days": 7})

    def test_fenced_json_with_prose(self):
        from agent.timecapsule import _coerce_extraction
        raw = 'Sure!\n```json\n{"capture": true, "kind": "commitment", "statement": "call mom", "callback_days": 3}\n```'
        out = _coerce_extraction(raw)
        self.assertIsNotNone(out)
        self.assertEqual(out["statement"], "call mom")
        self.assertEqual(out["kind"], "commitment")

    def test_capture_false_returns_none(self):
        from agent.timecapsule import _coerce_extraction
        self.assertIsNone(_coerce_extraction('{"capture": false}'))

    def test_garbage_returns_none(self):
        from agent.timecapsule import _coerce_extraction
        self.assertIsNone(_coerce_extraction("not json at all"))
        self.assertIsNone(_coerce_extraction(""))

    def test_missing_statement_returns_none(self):
        from agent.timecapsule import _coerce_extraction
        self.assertIsNone(_coerce_extraction('{"capture": true, "kind": "goal"}'))

    def test_invalid_kind_defaults_reflection(self):
        from agent.timecapsule import _coerce_extraction
        out = _coerce_extraction('{"capture": true, "kind": "banana", "statement": "x", "callback_days": 5}')
        self.assertEqual(out["kind"], "reflection")

    def test_callback_days_clamped(self):
        from agent.timecapsule import _coerce_extraction
        out = _coerce_extraction('{"capture": true, "kind": "goal", "statement": "x", "callback_days": 9999}')
        self.assertEqual(out["callback_days"], 365)
        out2 = _coerce_extraction('{"capture": true, "kind": "goal", "statement": "x", "callback_days": 0}')
        self.assertEqual(out2["callback_days"], 1)


class TestTurnText(unittest.TestCase):
    def test_dict_text(self):
        from agent.timecapsule import _turn_text
        self.assertEqual(_turn_text('{"text": "hello world"}'), "hello world")

    def test_plain_string(self):
        from agent.timecapsule import _turn_text
        self.assertEqual(_turn_text('"just a string"'), "just a string")

    def test_content_blocks(self):
        from agent.timecapsule import _turn_text
        self.assertEqual(
            _turn_text('[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]'),
            "a b",
        )


class TestHumanizeAge(unittest.TestCase):
    def test_phrasing(self):
        from agent.timecapsule import _humanize_age
        self.assertEqual(_humanize_age(0), "earlier today")
        self.assertEqual(_humanize_age(86400), "yesterday")
        self.assertEqual(_humanize_age(5 * 86400), "5 days ago")
        self.assertEqual(_humanize_age(7 * 86400), "7 days ago")
        self.assertEqual(_humanize_age(14 * 86400), "2 weeks ago")
        self.assertEqual(_humanize_age(21 * 86400), "3 weeks ago")
        self.assertEqual(_humanize_age(30 * 86400), "a month ago")
        self.assertEqual(_humanize_age(90 * 86400), "3 months ago")


# ── DB-backed behaviour ──────────────────────────────────────────────────────

class TestCaptureAndSurface(unittest.TestCase):
    def setUp(self):
        # Isolated temp DB for each test.
        import tempfile, os
        self._dir = tempfile.mkdtemp()
        self._db = os.path.join(self._dir, "tc.db")
        self._orig_db = longterm.DB_PATH
        longterm.DB_PATH = self._db
        longterm.init_db()
        from agent.timecapsule import _init_table
        _init_table()
        config.TIME_CAPSULE_ENABLED = True
        config.TIME_CAPSULE_MAX_PER_DAY = 2

    def tearDown(self):
        longterm.DB_PATH = self._orig_db

    def _insert_user_turn(self, text):
        with longterm._conn() as c:
            c.execute(
                "INSERT INTO turn_log (ts, session_id, turn_index, role, content_json) "
                "VALUES (?, 1, 0, 'user', ?)",
                (time.time(), f'{{"text": {text!r}}}'.replace("'", '"')),
            )

    def _count_capsules(self):
        with longterm._conn() as c:
            return c.execute("SELECT COUNT(*) FROM time_capsules").fetchone()[0]

    def test_capture_stores_goal(self):
        tc, _, _ = _mk_tc()
        tc._last_turn_id = 0
        self._insert_user_turn("I want to start running next week")
        tc._extract = lambda text: {"statement": "start running", "kind": "goal", "callback_days": 7}
        tc._capture_scan()
        self.assertEqual(self._count_capsules(), 1)
        with longterm._conn() as c:
            row = c.execute("SELECT statement, kind, status FROM time_capsules").fetchone()
        self.assertEqual(row[0], "start running")
        self.assertEqual(row[1], "goal")
        self.assertEqual(row[2], "pending")

    def test_chitchat_not_extracted(self):
        tc, _, _ = _mk_tc()
        tc._last_turn_id = 0
        self._insert_user_turn("can you summarize this document")

        def _boom(text):
            raise AssertionError("extract should not be called for chit-chat")

        tc._extract = _boom
        tc._capture_scan()
        self.assertEqual(self._count_capsules(), 0)

    def test_surface_due_speaks_and_marks_reminded(self):
        tc, spoken, toasted = _mk_tc()
        past = time.time() - 86400
        with longterm._conn() as c:
            c.execute(
                "INSERT INTO time_capsules (ts, statement, kind, callback_date, status) "
                "VALUES (?, 'start running', 'goal', ?, 'pending')",
                (past - 10 * 86400, past),
            )
        tc._surface_due()
        self.assertEqual(len(spoken), 1)
        self.assertIn("start running", spoken[0])
        self.assertEqual(len(toasted), 1)
        with longterm._conn() as c:
            status = c.execute("SELECT status FROM time_capsules").fetchone()[0]
        self.assertEqual(status, "reminded")

    def test_surface_skips_future_capsules(self):
        tc, spoken, _ = _mk_tc()
        future = time.time() + 5 * 86400
        with longterm._conn() as c:
            c.execute(
                "INSERT INTO time_capsules (ts, statement, kind, callback_date, status) "
                "VALUES (?, 'x', 'goal', ?, 'pending')",
                (time.time(), future),
            )
        tc._surface_due()
        self.assertEqual(len(spoken), 0)

    def test_daily_cap_throttles(self):
        tc, spoken, _ = _mk_tc()
        config.TIME_CAPSULE_MAX_PER_DAY = 1
        past = time.time() - 86400
        with longterm._conn() as c:
            for i in range(3):
                c.execute(
                    "INSERT INTO time_capsules (ts, statement, kind, callback_date, status) "
                    "VALUES (?, ?, 'goal', ?, 'pending')",
                    (past - 10 * 86400, f"goal {i}", past),
                )
        tc._surface_due()  # delivers one
        tc._surface_due()  # blocked by daily cap
        self.assertEqual(len(spoken), 1)

    def test_dedup_exact_text_when_no_embeddings(self):
        tc, _, _ = _mk_tc()
        with longterm._conn() as c:
            c.execute(
                "INSERT INTO time_capsules (ts, statement, kind, callback_date, status) "
                "VALUES (?, 'start running', 'goal', ?, 'pending')",
                (time.time(), time.time() + 86400),
            )
        # If embeddings are unavailable, dedup falls back to case-insensitive match.
        if longterm._embed("start running") is None:
            self.assertTrue(tc._is_duplicate("Start Running"))
            self.assertFalse(tc._is_duplicate("read more books"))


if __name__ == "__main__":
    unittest.main()
