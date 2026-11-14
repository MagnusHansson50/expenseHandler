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
    assert user_version(temp_db.DB_PATH) == db.SCHEMA_VERSION == 2
    assert "settings" in table_names(temp_db.DB_PATH)


def test_a_database_from_before_versioning_is_kept_and_stamped(temp_db):
    anna = temp_db.create_user("Anna")
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == db.SCHEMA_VERSION
    assert temp_db.get_user(anna).name == "Anna"


def test_init_db_can_run_again(temp_db):
    temp_db.init_db()
    temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == db.SCHEMA_VERSION


def test_a_database_from_a_newer_version_is_refused_and_left_alone(tmp_path, monkeypatch):
    path = tmp_path / "newer.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA user_version = 7")
        conn.commit()
    monkeypatch.setattr(db, "DB_PATH", path)

    with pytest.raises(db.DatabaseTooNew) as caught:
        db.init_db()
    assert caught.value.params == {"found": 7, "supported": db.SCHEMA_VERSION}
    assert user_version(path) == 7
    assert table_names(path) == set()  # nothing was created


def test_migrations_run_once_in_order_up_to_the_current_version(temp_db, monkeypatch):
    # Two made-up migrations after the real ones; the database is at the current version.
    current = db.SCHEMA_VERSION
    calls = []

    def add_note_column(conn):
        calls.append(current + 1)
        conn.execute("ALTER TABLE history ADD COLUMN note TEXT")

    def add_index(conn):
        calls.append(current + 2)
        conn.execute("CREATE INDEX idx_history_note ON history (note)")

    monkeypatch.setattr(db, "SCHEMA_VERSION", current + 2)
    monkeypatch.setattr(db, "_MIGRATIONS", {**db._MIGRATIONS, current + 1: add_note_column, current + 2: add_index})
    temp_db.init_db()
    temp_db.init_db()
    assert calls == [current + 1, current + 2]
    assert user_version(temp_db.DB_PATH) == current + 2


def test_a_failing_migration_changes_nothing(temp_db, monkeypatch):
    def half_done(conn):
        conn.execute("ALTER TABLE history ADD COLUMN note TEXT")
        raise sqlite3.OperationalError("disk full")

    current = db.SCHEMA_VERSION
    monkeypatch.setattr(db, "SCHEMA_VERSION", current + 1)
    monkeypatch.setattr(db, "_MIGRATIONS", {**db._MIGRATIONS, current + 1: half_done})
    with pytest.raises(sqlite3.OperationalError):
        temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == current
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(history)")]
    assert "note" not in columns


def test_a_version_1_database_gets_the_settings_table_and_keeps_its_data(temp_db):
    # As a desktop user's expenses.db from before version 2: no settings table.
    anna = temp_db.create_user("Anna", ["Mejeri"])
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        conn.execute("DROP TABLE settings")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    temp_db.init_db()
    assert user_version(temp_db.DB_PATH) == 2
    assert "settings" in table_names(temp_db.DB_PATH)
    assert temp_db.get_user(anna).name == "Anna"
    assert "Mejeri" in temp_db.get_categories(anna)
    assert temp_db.get_max_price(anna) == 100_000  # no choice made yet: the default


# --- Which file is used (EXPENSES_DB_PATH) ------------------------------------


@pytest.mark.parametrize("env", [{}, {"EXPENSES_DB_PATH": ""}, {"EXPENSES_DB_PATH": "   "}])
def test_without_expenses_db_path_the_file_next_to_the_code_is_used(env):
    assert db.database_path(env) == db.DEFAULT_DB_PATH
    assert db.DEFAULT_DB_PATH.name == "expenses.db"


def test_expenses_db_path_picks_another_file(tmp_path):
    assert db.database_path({"EXPENSES_DB_PATH": f" {tmp_path / 'other.db'} "}) == tmp_path / "other.db"
