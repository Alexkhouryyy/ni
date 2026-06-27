"""Tests for per-device access tokens (agent/access_tokens.py)."""
from agent import access_tokens as at, longterm


def test_issue_and_verify(test_db):
    at.init_db()
    token = at.issue(label="My phone")
    assert token.startswith("apxd_")
    assert at.verify(token) is True


def test_raw_token_never_stored(test_db):
    at.init_db()
    token = at.issue(label="laptop")
    # Only the hash is persisted — the raw token must not appear anywhere.
    with longterm._conn() as c:
        rows = c.execute("SELECT token_hash, label FROM access_tokens").fetchall()
    assert all(token not in str(r) for r in rows)


def test_revoke_cuts_off_one_device(test_db):
    at.init_db()
    keep = at.issue(label="keep")
    drop = at.issue(label="drop")
    drop_id = [t["id"] for t in at.list_tokens() if t["label"] == "drop"][0]

    assert at.revoke(drop_id) is True
    assert at.verify(drop) is False   # revoked device is cut off
    assert at.verify(keep) is True    # the others keep working


def test_verify_rejects_garbage(test_db):
    at.init_db()
    assert at.verify(None) is False
    assert at.verify("") is False
    assert at.verify("not-a-real-token") is False
    assert at.verify("apxd_fabricated") is False


def test_list_tokens_metadata_only(test_db):
    at.init_db()
    at.issue(label="a")
    rows = at.list_tokens()
    assert rows and set(rows[0].keys()) == {
        "id", "label", "device_id", "created_at", "last_used", "revoked"
    }
    assert "token_hash" not in rows[0]


def test_revoke_all(test_db):
    at.init_db()
    t1, t2 = at.issue(label="1"), at.issue(label="2")
    n = at.revoke_all()
    assert n == 2
    assert at.verify(t1) is False and at.verify(t2) is False
