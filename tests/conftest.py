import pytest

from integrations import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the data layer at a fresh database file for each test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_expenses.db")
    db.init_db()
    return db


@pytest.fixture
def two_users(temp_db):
    """Two users, Anna and Bo, returned as (anna_id, bo_id)."""
    return temp_db.create_user("Anna"), temp_db.create_user("Bo")
