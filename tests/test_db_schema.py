"""The schema version kept in the database file (PRAGMA user_version)."""

import sqlite3
from contextlib import closing

import pytest

from integrations import db


def user_version(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def table_names(path):
    with closing(sqlite3.connect(path)) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_a_new_database_gets_the_current_version(temp_db):
    assert user_version(temp_db.DB_PATH) == db.SCHEMA_VERSION == 1


def test_a_database_from_before_versioning_is_kept_and_stamped(temp_db):
    anna = temp_db.create_user("Anna")
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == 1
    assert temp_db.get_user(anna).name == "Anna"


def test_init_db_can_run_again(temp_db):
    temp_db.init_db()
    temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == 1


def test_a_database_from_a_newer_version_is_refused_and_left_alone(tmp_path, monkeypatch):
    path = tmp_path / "newer.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA user_version = 7")
        conn.commit()
    monkeypatch.setattr(db, "DB_PATH", path)

    with pytest.raises(db.DatabaseTooNew) as caught:
        db.init_db()
    assert caught.value.params == {"found": 7, "supported": 1}
    assert user_version(path) == 7
    assert table_names(path) == set()  # nothing was created


def test_migrations_run_once_in_order_up_to_the_current_version(temp_db, monkeypatch):
    calls = []

    def add_note_column(conn):
        calls.append(2)
        conn.execute("ALTER TABLE history ADD COLUMN note TEXT")

    def add_index(conn):
        calls.append(3)
        conn.execute("CREATE INDEX idx_history_note ON history (note)")

    monkeypatch.setattr(db, "SCHEMA_VERSION", 3)
    monkeypatch.setattr(db, "_MIGRATIONS", {2: add_note_column, 3: add_index})
    temp_db.init_db()
    temp_db.init_db()
    assert calls == [2, 3]
    assert user_version(temp_db.DB_PATH) == 3


def test_a_failing_migration_changes_nothing(temp_db, monkeypatch):
    def half_done(conn):
        conn.execute("ALTER TABLE history ADD COLUMN note TEXT")
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setattr(db, "_MIGRATIONS", {2: half_done})
    with pytest.raises(sqlite3.OperationalError):
        temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == 1
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(history)")]
    assert "note" not in columns


# --- Which file is used (EXPENSES_DB_PATH) ------------------------------------


@pytest.mark.parametrize("env", [{}, {"EXPENSES_DB_PATH": ""}, {"EXPENSES_DB_PATH": "   "}])
def test_without_expenses_db_path_the_file_next_to_the_code_is_used(env):
    assert db.database_path(env) == db.DEFAULT_DB_PATH
    assert db.DEFAULT_DB_PATH.name == "expenses.db"


def test_expenses_db_path_picks_another_file(tmp_path):
    assert db.database_path({"EXPENSES_DB_PATH": f" {tmp_path / 'other.db'} "}) == tmp_path / "other.db"
