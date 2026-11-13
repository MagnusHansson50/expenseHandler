"""services/history.py against a temporary database."""

import pandas as pd
import pytest

from integrations import db
from services import history


@pytest.fixture
def anna(temp_db):
    user_id = temp_db.create_user("Anna", ["Mejeri", "Dryck", "Snacks"])
    temp_db.save_receipt(
        user_id, "2026-11-01",
        pd.DataFrame([("Mjölk", 15.9, "Dryck"), ("Chips", 25.0, "Mejeri")], columns=["Item", "Price", "Category"]),
        {},
    )
    return user_id


def test_changed_categories_are_saved_and_remembered(anna):
    shown = db.get_all_history(anna)
    changed = history.change_categories(anna, shown, {"edited_rows": {1: {"Category": "Snacks"}}}, "sv")
    assert changed == (1, 0)
    assert db.get_all_history(anna)["Category"].tolist() == ["Dryck", "Snacks"]
    assert db.load_memory(anna) == {"Chips": "Snacks"}


def test_no_change_does_not_touch_the_database(anna, monkeypatch):
    monkeypatch.setattr(db, "update_history_categories", lambda *_: pytest.fail("nothing to save"))
    shown = db.get_all_history(anna)
    assert history.change_categories(anna, shown, {"edited_rows": {0: {"Category": "Dryck"}}}, "sv") == (0, 0)


# --- The list changed in the database after it was shown (e.g. another tab) -----


def delete_purchase(user_id, item):
    """Delete one purchase behind the list's back, as another tab could."""
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        conn.execute("DELETE FROM history WHERE user_id = ? AND item = ?", (user_id, item))


def test_edits_are_mapped_on_the_list_as_it_was_shown(anna):
    shown = db.get_all_history(anna)  # row 0 Mjölk, row 1 Chips
    delete_purchase(anna, "Mjölk")  # now Chips would be row 0 in a list loaded again
    result = history.change_categories(anna, shown, {"edited_rows": {1: {"Category": "Snacks"}}}, "sv")
    assert result == (1, 0)
    assert db.get_all_history(anna)[["Item", "Category"]].values.tolist() == [["Chips", "Snacks"]]


def test_an_edited_purchase_that_no_longer_exists_is_counted_as_missing(anna):
    shown = db.get_all_history(anna)
    delete_purchase(anna, "Mjölk")
    result = history.change_categories(anna, shown, {"edited_rows": {0: {"Category": "Snacks"}}}, "sv")
    assert result == (0, 1)
    assert db.get_all_history(anna)["Category"].tolist() == ["Mejeri"]  # Chips untouched
    assert db.load_memory(anna) == {}
