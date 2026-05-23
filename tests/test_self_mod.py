"""Unit tests for agent/self_mod.py — runtime self-modification (prompt + tools)."""
import json
import pytest
from pathlib import Path

from agent import self_mod


@pytest.fixture(autouse=True)
def isolated_overlay(tmp_path, monkeypatch):
    """Point OVERLAY_PATH and BACKUP_PATH at temp files so tests never touch ~/.voice_agent_overlay.json."""
    overlay = tmp_path / "overlay.json"
    backup = tmp_path / "overlay.backup.json"
    monkeypatch.setattr(self_mod, "OVERLAY_PATH", overlay)
    monkeypatch.setattr(self_mod, "BACKUP_PATH", backup)
    # Reset in-memory handler registry between tests
    self_mod._dynamic_tool_handlers.clear()
    yield overlay, backup
    self_mod._dynamic_tool_handlers.clear()


# ── _load / _save ──────────────────────────────────────────────────────────

class TestLoadSave:
    def test_missing_file_returns_default(self, isolated_overlay):
        result = self_mod._load()
        assert result == {"prompt_addition": "", "tools": []}

    def test_corrupted_json_returns_default(self, isolated_overlay):
        overlay, _ = isolated_overlay
        overlay.write_text("not valid json {{{{")
        result = self_mod._load()
        assert result == {"prompt_addition": "", "tools": []}

    def test_save_writes_json(self, isolated_overlay):
        overlay, _ = isolated_overlay
        self_mod._save({"prompt_addition": "hello", "tools": []})
        data = json.loads(overlay.read_text())
        assert data["prompt_addition"] == "hello"

    def test_save_creates_backup(self, isolated_overlay):
        overlay, backup = isolated_overlay
        # Write initial file so there is something to back up
        overlay.write_text(json.dumps({"prompt_addition": "old", "tools": []}))
        self_mod._save({"prompt_addition": "new", "tools": []})
        assert backup.exists()
        assert json.loads(backup.read_text())["prompt_addition"] == "old"


# ── update_system_prompt ───────────────────────────────────────────────────

class TestUpdateSystemPrompt:
    def test_append_to_empty(self):
        result = self_mod.update_system_prompt("Be concise.")
        assert "updated" in result.lower()
        assert self_mod.get_prompt_addition() == "Be concise."

    def test_append_adds_newlines_between(self):
        self_mod.update_system_prompt("First rule.")
        self_mod.update_system_prompt("Second rule.")
        addition = self_mod.get_prompt_addition()
        assert "First rule." in addition
        assert "Second rule." in addition
        assert "\n\n" in addition

    def test_replace_overwrites_previous(self):
        self_mod.update_system_prompt("Old rule.")
        self_mod.update_system_prompt("New rule.", replace=True)
        assert self_mod.get_prompt_addition() == "New rule."

    def test_char_count_in_return_message(self):
        result = self_mod.update_system_prompt("X" * 50)
        assert "50" in result


# ── register_new_tool ──────────────────────────────────────────────────────

_GOOD_CODE = "def run(inputs):\n    return 'hello ' + str(inputs.get('name','world'))"
_BAD_CODE   = "def not_run(inputs):\n    return 'oops'"
_RAISES_CODE = "def run(inputs):\n    raise ValueError('boom')"


class TestRegisterNewTool:
    def test_happy_path_registers_handler(self):
        result = self_mod.register_new_tool("greeter", "Says hi", {}, _GOOD_CODE)
        assert "Registered" in result
        assert "greeter" in self_mod._dynamic_tool_handlers

    def test_tool_is_callable(self):
        self_mod.register_new_tool("greeter", "Says hi", {}, _GOOD_CODE)
        out = self_mod.dispatch("greeter", {"name": "Alice"})
        assert out == "hello Alice"

    def test_invalid_identifier_rejected(self):
        result = self_mod.register_new_tool("not-valid", "bad", {}, _GOOD_CODE)
        assert "Invalid" in result

    def test_reserved_name_rejected(self):
        result = self_mod.register_new_tool("bash", "shell", {}, _GOOD_CODE)
        assert "Reserved" in result

    def test_mcp_prefix_rejected(self):
        result = self_mod.register_new_tool("mcp__mytool", "mcp", {}, _GOOD_CODE)
        assert "Reserved" in result

    def test_missing_run_function_rejected(self):
        result = self_mod.register_new_tool("norun", "no run", {}, _BAD_CODE)
        assert "invalid" in result.lower()

    def test_re_register_replaces_existing(self):
        self_mod.register_new_tool("tool1", "v1", {}, "def run(inputs): return 'v1'")
        self_mod.register_new_tool("tool1", "v2", {}, "def run(inputs): return 'v2'")
        out = self_mod.dispatch("tool1", {})
        assert out == "v2"
        # Only one record in overlay
        overlay = self_mod._load()
        assert len([t for t in overlay["tools"] if t["name"] == "tool1"]) == 1

    def test_persists_to_overlay_file(self):
        self_mod.register_new_tool("persistent", "persists", {}, _GOOD_CODE)
        overlay = self_mod._load()
        assert any(t["name"] == "persistent" for t in overlay["tools"])


# ── dispatch ───────────────────────────────────────────────────────────────

class TestDispatch:
    def test_unknown_tool_returns_none(self):
        assert self_mod.dispatch("nonexistent", {}) is None

    def test_known_tool_returns_result(self):
        self_mod.register_new_tool("echo", "echoes", {}, "def run(inputs): return inputs.get('msg','?')")
        assert self_mod.dispatch("echo", {"msg": "hi"}) == "hi"

    def test_raising_tool_returns_error_string(self):
        self_mod.register_new_tool("raiser", "raises", {}, _RAISES_CODE)
        result = self_mod.dispatch("raiser", {})
        assert "error" in result.lower()
        assert "boom" in result


# ── get_dynamic_tools ──────────────────────────────────────────────────────

class TestGetDynamicTools:
    def test_empty_when_no_tools(self):
        assert self_mod.get_dynamic_tools() == []

    def test_returns_claude_compatible_dicts(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": []}
        self_mod.register_new_tool("shaped", "has schema", schema, _GOOD_CODE)
        tools = self_mod.get_dynamic_tools()
        assert len(tools) == 1
        t = tools[0]
        assert t["name"] == "shaped"
        assert "description" in t
        assert "input_schema" in t
        # code must NOT be exposed — it's an impl detail
        assert "code" not in t


# ── load_dynamic_handlers ──────────────────────────────────────────────────

class TestLoadDynamicHandlers:
    def test_loads_handlers_from_overlay(self):
        self_mod.register_new_tool("preloaded", "d", {}, _GOOD_CODE)
        # Clear in-memory handlers to simulate a fresh process startup
        self_mod._dynamic_tool_handlers.clear()
        count = self_mod.load_dynamic_handlers()
        assert count == 1
        assert "preloaded" in self_mod._dynamic_tool_handlers

    def test_skips_bad_tool_code_gracefully(self):
        # Manually write a broken tool to the overlay
        overlay = self_mod._load()
        overlay["tools"].append({"name": "broken", "description": "d", "code": "syntax error {{{"})
        self_mod._save(overlay)
        self_mod._dynamic_tool_handlers.clear()
        count = self_mod.load_dynamic_handlers()
        assert count == 0
        assert "broken" not in self_mod._dynamic_tool_handlers


# ── revert ─────────────────────────────────────────────────────────────────

class TestRevert:
    def test_hard_reset_clears_everything(self):
        self_mod.update_system_prompt("Custom rule.")
        self_mod.register_new_tool("mytool", "d", {}, _GOOD_CODE)
        self_mod.revert(restore_backup=False)
        assert self_mod.get_prompt_addition() == ""
        assert self_mod.get_dynamic_tools() == []
        assert self_mod._dynamic_tool_handlers == {}

    def test_restore_backup_recovers_previous_state(self, isolated_overlay):
        overlay_path, _ = isolated_overlay
        # First write — this becomes the backup when we write a second time
        self_mod.update_system_prompt("Original rule.")
        # Second write — backs up "Original rule." and overwrites
        self_mod.update_system_prompt("New rule.", replace=True)
        # Now revert to backup
        result = self_mod.revert(restore_backup=True)
        assert "Restored" in result
        assert self_mod.get_prompt_addition() == "Original rule."

    def test_restore_backup_no_file_falls_through(self, isolated_overlay):
        _, backup = isolated_overlay
        # No backup file exists → should hard reset instead
        assert not backup.exists()
        result = self_mod.revert(restore_backup=True)
        # Either "cleared" or "restored" — no crash
        assert isinstance(result, str)


# ── show ───────────────────────────────────────────────────────────────────

class TestShow:
    def test_empty_show(self):
        s = self_mod.show()
        assert s["prompt_addition_chars"] == 0
        assert s["dynamic_tools"] == []

    def test_show_after_changes(self):
        self_mod.update_system_prompt("A" * 100)
        self_mod.register_new_tool("mytool", "d", {}, _GOOD_CODE)
        s = self_mod.show()
        assert s["prompt_addition_chars"] == 100
        assert "mytool" in s["dynamic_tools"]
        assert len(s["prompt_addition_preview"]) <= 300
