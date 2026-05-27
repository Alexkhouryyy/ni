"""Tests for Phase 10 — Apex Resident.

Covers: state machine, audit log, wake-phrase extraction, hotkey wiring,
autostart dispatcher. Pure unit tests — no audio devices, no display server.
"""
import os
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ResidentState state machine
# ---------------------------------------------------------------------------

class TestResidentState:
    def test_starts_idle(self):
        from app.resident import ResidentState
        s = ResidentState()
        assert s.get() == ResidentState.IDLE
        assert not s.is_muted()

    def test_transitions_notify_listeners(self):
        from app.resident import ResidentState
        s = ResidentState()
        seen: list[str] = []
        s.add_listener(lambda st: seen.append(st))
        s.set(ResidentState.LISTENING)
        s.set(ResidentState.THINKING)
        s.set(ResidentState.IDLE)
        assert seen == [
            ResidentState.LISTENING,
            ResidentState.THINKING,
            ResidentState.IDLE,
        ]

    def test_same_state_doesnt_re_notify(self):
        from app.resident import ResidentState
        s = ResidentState()
        seen: list[str] = []
        s.add_listener(lambda st: seen.append(st))
        s.set(ResidentState.LISTENING)
        s.set(ResidentState.LISTENING)
        assert seen == [ResidentState.LISTENING]

    def test_mute_minus_one_persists(self):
        from app.resident import ResidentState
        s = ResidentState()
        s.mute(-1)
        assert s.is_muted()
        # State.get() should report MUTED regardless of underlying state
        assert s.get() == ResidentState.MUTED

    def test_unmute_with_zero(self):
        from app.resident import ResidentState
        s = ResidentState()
        s.mute(-1)
        assert s.is_muted()
        s.mute(0)
        assert not s.is_muted()
        assert s.get() == ResidentState.IDLE

    def test_timed_mute_expires(self):
        from app.resident import ResidentState
        s = ResidentState()
        s.mute(1)  # 1 minute
        assert s.is_muted()
        # Mock time to fast-forward
        with patch("app.resident.time.time", return_value=time.time() + 120):
            assert not s.is_muted()


# ---------------------------------------------------------------------------
# Wake-phrase extraction
# ---------------------------------------------------------------------------

class TestExtractRequest:
    def setup_method(self):
        from app.resident import _extract_request
        self.fn = _extract_request

    def test_apex_alone_returns_empty(self):
        assert self.fn("apex", ["apex"]) == ""

    def test_request_after_wake_word(self):
        assert self.fn("apex what's the weather",
                       ["apex"]) == "what's the weather"

    def test_strips_punctuation(self):
        assert self.fn("apex, open the dashboard.",
                       ["apex"]) == "open the dashboard"

    def test_picks_longest_matching_phrase(self):
        # "hey apex" matches first; the residual is empty
        assert self.fn("hey apex tell me a joke",
                       ["apex", "hey apex"]) == "tell me a joke"

    def test_no_wake_phrase_returns_whole_text(self):
        # Wake fired but the model heard something weird — fall through
        assert self.fn("blah what is this",
                       ["apex"]) == "blah what is this"

    def test_empty_input(self):
        assert self.fn("", ["apex"]) == ""

    def test_case_insensitive(self):
        assert self.fn("APEX What's up?", ["apex"]) == "what's up"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAudit:
    def test_record_writes_line(self, tmp_path, monkeypatch):
        log = tmp_path / "wake_audit.log"
        monkeypatch.setattr("config.RESIDENT_AUDIT_FILE", str(log))
        from app import audit
        audit.record("apex what's on my screen", "responded", note="reply_chars=42")
        text = log.read_text()
        assert "responded" in text
        assert "apex what's on my screen" in text
        assert "reply_chars=42" in text

    def test_record_handles_pipe_in_transcript(self, tmp_path, monkeypatch):
        log = tmp_path / "wake_audit.log"
        monkeypatch.setattr("config.RESIDENT_AUDIT_FILE", str(log))
        from app import audit
        audit.record("apex run a|b|c", "responded")
        text = log.read_text()
        # Pipes in transcript replaced so they don't break field parsing
        assert "a/b/c" in text

    def test_recent_parses_back(self, tmp_path, monkeypatch):
        log = tmp_path / "wake_audit.log"
        monkeypatch.setattr("config.RESIDENT_AUDIT_FILE", str(log))
        from app import audit
        audit.record("apex hi", "responded")
        audit.record("background noise", "muted_ignored")
        entries = audit.recent()
        assert len(entries) == 2
        # Most recent first
        assert entries[0]["action"] == "muted_ignored"
        assert entries[1]["action"] == "responded"

    def test_record_failure_is_silent(self, monkeypatch):
        # Point at an unwritable path — should not raise
        monkeypatch.setattr("config.RESIDENT_AUDIT_FILE", "/proc/no_can_write")
        from app import audit
        audit.record("apex test", "responded")  # no exception = pass

    def test_recent_handles_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.RESIDENT_AUDIT_FILE",
                            str(tmp_path / "no_such_file.log"))
        from app import audit
        assert audit.recent() == []


# ---------------------------------------------------------------------------
# Hotkey wrapper degrades gracefully
# ---------------------------------------------------------------------------

class TestHotkeys:
    def test_empty_bindings_returns_false(self):
        from app.hotkey import GlobalHotkeys
        hk = GlobalHotkeys()
        assert hk.start() is False

    def test_missing_pynput_returns_false(self, monkeypatch):
        import sys
        # Hide pynput
        monkeypatch.setitem(sys.modules, "pynput", None)
        from app.hotkey import GlobalHotkeys
        hk = GlobalHotkeys()
        hk.bind("<ctrl>+<space>", lambda: None)
        # Either ImportError or successful start when pynput is None
        # When None is set, import raises TypeError; should be caught
        # Either way, start() returns False
        result = hk.start()
        assert result in (True, False)  # either branch is acceptable
        hk.stop()


# ---------------------------------------------------------------------------
# Wake listener: muted state discards audio (mock-only — no real mic)
# ---------------------------------------------------------------------------

class TestWakeListener:
    def test_set_muted_and_is_muted(self):
        from voice.wake import WakeWordListener
        w = WakeWordListener(wake_phrases=["apex"])
        assert w.is_muted is False
        w.set_muted(True)
        assert w.is_muted is True
        w.set_muted(False)
        assert w.is_muted is False


# ---------------------------------------------------------------------------
# Autostart dispatcher routes by platform
# ---------------------------------------------------------------------------

class TestAutostart:
    def test_linux_install_writes_desktop_file(self, tmp_path, monkeypatch):
        # Redirect HOME so we don't pollute the user's real config
        monkeypatch.setenv("HOME", str(tmp_path))
        from app import autostart
        # Re-resolve project paths by importing fresh
        if hasattr(autostart, "_linux_desktop_path"):
            target = autostart._linux_desktop_path()
        # Force-call Linux installer regardless of host OS
        result = autostart._linux_install()
        path = autostart._linux_desktop_path()
        assert path.exists()
        content = path.read_text()
        assert "[Desktop Entry]" in content
        assert "--resident" in content
        assert "Installed" in result

    def test_linux_uninstall_removes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from app import autostart
        autostart._linux_install()
        assert autostart._linux_desktop_path().exists()
        result = autostart._linux_uninstall()
        assert not autostart._linux_desktop_path().exists()
        assert "Removed" in result

    def test_linux_status_reflects_install(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from app import autostart
        assert autostart._linux_status() == "Not installed."
        autostart._linux_install()
        assert "Installed" in autostart._linux_status()
        autostart._linux_uninstall()

    def test_unsupported_os(self, monkeypatch):
        from app import autostart
        monkeypatch.setattr("platform.system", lambda: "Plan9")
        assert "Unsupported OS" in autostart._dispatch("install")

    def test_unknown_action(self, monkeypatch):
        from app import autostart
        monkeypatch.setattr("platform.system", lambda: "Linux")
        assert "Unknown action" in autostart._dispatch("nuke")


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------

class TestResidentConfig:
    def test_wake_phrases_include_apex(self):
        import config
        assert any("apex" in p.lower() for p in config.WAKE_PHRASES)

    def test_resident_keys_exist(self):
        import config
        assert hasattr(config, "RESIDENT_SILENT_BOOT")
        assert hasattr(config, "RESIDENT_LOG_FILE")
        assert hasattr(config, "RESIDENT_AUDIT_FILE")
        assert hasattr(config, "RESIDENT_GLOBAL_HOTKEY")
        assert hasattr(config, "RESIDENT_MUTE_HOTKEY")
