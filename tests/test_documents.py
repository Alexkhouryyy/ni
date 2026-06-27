"""Tests for the writing-first documents store + AI edit (agent/documents.py)."""
from agent import documents as docs, provider


def test_create_get_update_delete(test_db):
    docs.init_db()
    d = docs.create("My Essay", "# Hello\n\nFirst draft.")
    assert d["id"] and d["title"] == "My Essay"

    got = docs.get(d["id"])
    assert got["content"].startswith("# Hello")

    up = docs.update(d["id"], content="# Hello\n\nSecond draft.")
    assert "Second" in up["content"]
    assert up["updated_at"] >= got["updated_at"]

    assert docs.delete(d["id"]) is True
    assert docs.get(d["id"]) is None


def test_list_orders_by_updated_and_has_meta(test_db):
    docs.init_db()
    a = docs.create("A", "one two three")
    b = docs.create("B", "four five")
    docs.update(a["id"], content="one two three four five six")  # bump A to top
    rows = docs.list_documents()
    assert rows[0]["id"] == a["id"]
    assert rows[0]["words"] == 6
    assert "snippet" in rows[0] and "content" not in rows[0]


def test_ai_edit_uses_preset(test_db, monkeypatch):
    captured = {}

    def fake_complete(model, system, user, max_tokens=2048):
        captured["system"] = system
        captured["user"] = user
        return "polished text"

    monkeypatch.setattr(provider, "complete", fake_complete)
    out = docs.ai_edit("rough text", preset="improve")
    assert out["result"] == "polished text"
    assert "Improve the clarity" in captured["user"]
    assert "rough text" in captured["user"]


def test_ai_edit_custom_instruction(test_db, monkeypatch):
    monkeypatch.setattr(provider, "complete", lambda m, s, u, max_tokens=2048: "done")
    out = docs.ai_edit("text", instruction="translate to French")
    assert out["result"] == "done"


def test_ai_edit_requires_something(test_db):
    assert "error" in docs.ai_edit("some text", preset="", instruction="")
    assert "error" in docs.ai_edit("", preset="improve")


def test_ai_edit_handles_provider_error(test_db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no api key")
    monkeypatch.setattr(provider, "complete", boom)
    out = docs.ai_edit("text", preset="improve")
    assert "error" in out and "no api key" in out["error"]
