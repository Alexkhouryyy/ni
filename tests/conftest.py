"""Shared pytest fixtures."""
import pytest
from agent import safety, longterm


@pytest.fixture(autouse=True)
def block_safety_stdin():
    """Prevent safety.check() from calling input() during the test suite.

    Default is deny-all; individual tests that want to confirm an action call
    safety.set_confirm_fn(lambda _: True) themselves.
    """
    original = safety._confirm_fn
    safety.set_confirm_fn(lambda _prompt: False)
    yield
    safety._confirm_fn = original


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Temporary SQLite DB for tests that touch longterm / turn_log.

    Patches longterm.DB_PATH so the production DB is never read or written.
    All tables are created fresh via init_db().
    """
    db_path = str(tmp_path / "test_memory.db")
    monkeypatch.setattr(longterm, "DB_PATH", db_path)
    longterm.init_db()
    return db_path
