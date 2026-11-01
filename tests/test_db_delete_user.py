"""Deleting a user in the data layer. Hashes here are fake bytes; no real passwords."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from integrations import db

HASH, SALT = b"hash" * 16, b"salt" * 4
TABLES = ("users", "categories", "memory", "history", "credentials")


def rows_per_table(user_id):
    """How many rows each table has for this user."""
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        counts = {"users": conn.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,)).fetchone()[0]}
        for table in TABLES[1:]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)).fetchone()[0]
    return counts


@pytest.fixture
def anna_and_bo(temp_db):
    """Anna and Bo, each with a password, categories, memory and history."""
    users = []
    for name in ("Anna", "Bo"):
        user_id = temp_db.create_user_with_password(name, HASH, SALT, ["Food"])
        items = pd.DataFrame({"Item": [f"{name}s secret item"], "Price": [10.0], "Category": ["Food"]})
        temp_db.save_receipt(user_id, date(2026, 11, 1), items, {f"{name}s secret item": "Food"})
        users.append(user_id)
    return users


def test_all_data_of_the_user_is_deleted(anna_and_bo):
    anna, _ = anna_and_bo
    assert all(count > 0 for count in rows_per_table(anna).values())
    assert db.delete_user(anna) is True
    assert rows_per_table(anna) == dict.fromkeys(TABLES, 0)
    assert db.get_user(anna) is None
    assert db.get_login("Anna") is None


def test_another_users_data_is_untouched(anna_and_bo):
    anna, bo = anna_and_bo
    before = rows_per_table(bo)
    db.delete_user(anna)
    assert rows_per_table(bo) == before
    assert db.get_login("Bo").user.name == "Bo"
    assert db.load_memory(bo) == {"Bos secret item": "Food"}


def test_unknown_user_returns_false_and_deletes_nothing(anna_and_bo):
    assert db.delete_user(9999) is False
    assert [user.name for user in db.get_users()] == ["Anna", "Bo"]


def test_name_can_be_registered_again(anna_and_bo):
    anna, _ = anna_and_bo
    db.delete_user(anna)
    new_anna = db.create_user_with_password("anna", HASH, SALT, [])
    assert new_anna != anna
    assert db.get_history_dates(new_anna) == []


def test_deleted_data_is_overwritten_in_the_database_file(anna_and_bo):
    anna, _ = anna_and_bo
    db.delete_user(anna)
    content = Path(db.DB_PATH).read_bytes()
    assert b"Annas secret item" not in content
    assert b"Bos secret item" in content  # the check would find data that is still there
