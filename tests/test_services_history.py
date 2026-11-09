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
    assert changed == 1
    assert db.get_all_history(anna)["Category"].tolist() == ["Dryck", "Snacks"]
    assert db.load_memory(anna) == {"Chips": "Snacks"}


def test_no_change_does_not_touch_the_database(anna, monkeypatch):
    monkeypatch.setattr(db, "update_history_categories", lambda *_: pytest.fail("nothing to save"))
    shown = db.get_all_history(anna)
    assert history.change_categories(anna, shown, {"edited_rows": {0: {"Category": "Dryck"}}}, "sv") == 0
