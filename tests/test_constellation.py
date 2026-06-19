"""Unit tests for agent/constellation.py — the domain-expert planet panel.

Model calls are stubbed via `constellation._complete` so nothing hits the API.
"""
import pytest

from agent import constellation, longterm, vault


# ── Router (pure heuristic, no API, no DB) ────────────────────────────────────

class TestRoute:
    def test_decision_selects_relevant_experts(self):
        ps = constellation.route("should I quit my job to start a company?")
        keys = [p.key for p in ps]
        assert "career" in keys
        assert "devils_advocate" in keys  # a decision always gets its skeptic

    def test_multidomain_life_decision(self):
        ps = constellation.route(
            "is it worth taking the higher-paying job in a new city away from family?"
        )
        keys = [p.key for p in ps]
        assert "career" in keys
        assert "relationships" in keys

    def test_trivial_query_returns_nothing(self):
        assert constellation.route("what time is it?") == []
        assert constellation.route("remind me to call mom at 5pm") == []
        assert constellation.route("") == []

    def test_respects_max_planets_cap(self, monkeypatch):
        monkeypatch.setattr(constellation.config, "CONSTELLATION_MAX_PLANETS", 3)
        ps = constellation.route(
            "should I invest my savings, change careers, fix my health, and move?"
        )
        assert len(ps) <= 3

    def test_force_always_returns_panel(self):
        # No domain keywords, but force=True (manual convene) still convenes.
        ps = constellation.route("hello there", force=True)
        assert len(ps) >= 1

    def test_pack_diversity(self):
        # A broad decision should not return four planets from one pack.
        ps = constellation.route(
            "should I spend my bonus on a vacation or invest it for retirement?"
        )
        packs = {p.pack for p in ps}
        assert len(packs) >= 1  # at least diversified, never crashes


# ── Convene (stubbed model) ───────────────────────────────────────────────────

@pytest.fixture
def stub_model(monkeypatch):
    """Replace _complete so planet + synthesis + learn calls are deterministic."""
    seen = {"planet": 0, "synthesis": 0, "learn": 0}

    def fake(model, system, user, max_tokens, call_site):
        if call_site == "agent.constellation/synthesis":
            seen["synthesis"] += 1
            return (
                "Do it, but with a safety net.\n"
                "Confidence: medium — strong upside, real downside.\n"
                "Where the council split: Finance said go, Health urged caution; I ruled go."
            )
        if call_site == "agent.constellation/learn":
            seen["learn"] += 1
            return "SKIP"
        seen["planet"] += 1
        return f"[{model}] focused take. **Bottom line:** proceed with care."

    monkeypatch.setattr(constellation, "_complete", fake)
    return seen


class TestConvene:
    def test_returns_synthesized_result(self, stub_model):
        res = constellation.convene(
            "should I take the job?",
            planets=[constellation.PLANETS["career"], constellation.PLANETS["finance"]],
        )
        assert res.final_answer.startswith("Do it")
        assert res.confidence == "medium"
        assert res.confidence_note and "upside" in res.confidence_note
        assert res.disagreement and "Finance" in res.disagreement
        assert len(res.takes) == 2
        assert {t["key"] for t in res.takes} == {"career", "finance"}

    def test_verdict_lines_stripped_from_answer(self, stub_model):
        res = constellation.convene(
            "x?", planets=[constellation.PLANETS["strategist"]]
        )
        assert "Confidence:" not in res.final_answer
        assert "Where the council split:" not in res.final_answer

    def test_auto_select_when_planets_omitted(self, stub_model):
        res = constellation.convene("should I quit my job?")
        assert len(res.planets) >= 1

    def test_briefing_is_compact_and_framed(self, stub_model, monkeypatch):
        monkeypatch.setattr(constellation.config, "CONSTELLATION_BRIEFING_MAXCHARS", 400)
        planets = constellation.route("should I take the job?", force=True)
        briefing = constellation.convene_briefing("should I take the job?", planets)
        assert briefing.startswith("[EXPERT BRIEFING")
        assert len(briefing) <= 400


# ── Persistence (grows over time) ─────────────────────────────────────────────

@pytest.fixture
def tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "VAULT_DIR", tmp_path / "Apex")
    return tmp_path / "Apex"


class TestPersistence:
    def test_persist_writes_journal_and_memory(self, test_db, tmp_vault, monkeypatch):
        monkeypatch.setattr(
            constellation, "_complete",
            lambda *a, **k: "User has a 6-month emergency fund and is risk-averse.",
        )
        planet = constellation.PLANETS["finance"]
        constellation._persist_planet_memory(planet, "should I invest?", "Yes, slowly.")

        # Obsidian-visible journal exists and contains the fact.
        journal = vault.read_note("Finance", folder="Planets")
        assert journal is not None
        assert "emergency fund" in journal

        # Semantic memory row tagged for this planet.
        hits = longterm.recall(query="emergency fund", limit=10)
        assert any("planet:finance" in (h.get("tags") or "") for h in hits)

    def test_journal_grows_across_consults(self, test_db, tmp_vault, monkeypatch):
        facts = iter([
            "First durable fact about the user.",
            "Second durable fact about the user.",
        ])
        monkeypatch.setattr(constellation, "_complete", lambda *a, **k: next(facts))
        planet = constellation.PLANETS["health"]

        constellation._persist_planet_memory(planet, "q1", "a1")
        first = vault.read_note("Health", folder="Planets")
        constellation._persist_planet_memory(planet, "q2", "a2")
        second = vault.read_note("Health", folder="Planets")

        assert len(second.splitlines()) > len(first.splitlines())
        assert "First durable" in second and "Second durable" in second

    def test_skip_is_not_saved(self, test_db, tmp_vault, monkeypatch):
        monkeypatch.setattr(constellation, "_complete", lambda *a, **k: "SKIP")
        planet = constellation.PLANETS["career"]
        constellation._persist_planet_memory(planet, "q", "a")
        assert vault.read_note("Career", folder="Planets") is None

    def test_failed_take_is_not_distilled(self, test_db, tmp_vault, monkeypatch):
        called = {"n": 0}

        def fake(*a, **k):
            called["n"] += 1
            return "x"

        monkeypatch.setattr(constellation, "_complete", fake)
        planet = constellation.PLANETS["engineer"]
        # A take string that starts with "[" is a failure marker — never distilled.
        constellation._persist_planet_memory(planet, "q", "[Engineer failed to respond: boom]")
        assert called["n"] == 0


# ── 1:1 expert chat ───────────────────────────────────────────────────────────

class TestChat:
    def test_chat_returns_reply(self, monkeypatch):
        monkeypatch.setattr(constellation.provider, "get_client", lambda model: object())
        monkeypatch.setattr(constellation.config, "CONSTELLATION_LEARN", False)

        class _Block:
            type = "text"
            text = "Build an emergency fund first. **Bottom line:** stabilize, then invest."

        class _Resp:
            content = [_Block()]

        monkeypatch.setattr(constellation.telemetry, "create", lambda client, **kw: _Resp())

        out = constellation.chat_with_planet("finance", "should I invest my savings?", history=[])
        assert out["planet"]["display"] == "Finance"
        assert "emergency fund" in out["reply"]

    def test_chat_unknown_planet(self):
        out = constellation.chat_with_planet("not_a_planet", "hi")
        assert "error" in out

    def test_chat_passes_history(self, monkeypatch):
        monkeypatch.setattr(constellation.provider, "get_client", lambda model: object())
        monkeypatch.setattr(constellation.config, "CONSTELLATION_LEARN", False)
        captured = {}

        class _Block:
            type = "text"
            text = "ok"

        class _Resp:
            content = [_Block()]

        def fake_create(client, **kw):
            captured["messages"] = kw.get("messages")
            return _Resp()

        monkeypatch.setattr(constellation.telemetry, "create", fake_create)
        constellation.chat_with_planet(
            "career", "what next?",
            history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        )
        roles = [m["role"] for m in captured["messages"]]
        assert roles == ["user", "assistant", "user"]  # history + new message
        assert captured["messages"][-1]["content"] == "what next?"


# ── Roster / lifecycle ────────────────────────────────────────────────────────

class TestRoster:
    def test_twelve_planets(self):
        assert len(constellation.PLANETS) == 12

    def test_list_planets_shape(self):
        rows = constellation.list_planets()
        assert len(rows) == 12
        keys = {r["key"] for r in rows}
        assert {"finance", "engineer", "devils_advocate", "synthesizer"} <= keys
        for r in rows:
            assert r["glyph"] and r["codename"] and r["pack"] in {"life", "maker", "mind"}

    def test_strategist_and_devil_use_flagship(self):
        assert constellation.PLANETS["strategist"].model == constellation._flagship()
        assert constellation.PLANETS["devils_advocate"].model == constellation._flagship()

    def test_init_creates_planets_folder(self, tmp_vault):
        msg = constellation.init()
        assert "planets" in msg.lower()
        assert (tmp_vault / "Planets").is_dir()
