"""Changing the category of saved purchases (db.update_history_categories)."""

import sqlite3

import pandas as pd
import pytest

from core.constants import FALLBACK_CATEGORY
from integrations import db


def receipt(*rows):
    return pd.DataFrame(rows, columns=["Item", "Price", "Category"])


@pytest.fixture
def anna_and_bo(temp_db):
    """Anna and Bo with the same categories, each with saved purchases."""
    anna = temp_db.create_user("Anna", ["Mejeri", "Dryck", "Snacks"])
    bo = temp_db.create_user("Bo", ["Mejeri", "Dryck", "Snacks"])
    temp_db.save_receipt(
        anna, "2026-11-01",
        receipt(("Mjölk", 15.9, "Dryck"), ("Chips", 25.0, "Mejeri"), ("Mjölk", 15.9, "Dryck")),
        {"Mjölk": "Dryck", "Chips": "Mejeri"},
    )
    temp_db.save_receipt(bo, "2026-11-01", receipt(("Mjölk", 15.9, "Dryck"),), {"Mjölk": "Dryck"})
    return anna, bo


def ids_and_categories(user_id):
    history = db.get_all_history(user_id)
    return dict(zip(history["Id"], history["Category"], strict=True))


def ids_of(user_id, item):
    history = db.get_all_history(user_id)
    return history.loc[history["Item"] == item, "Id"].tolist()


def test_changes_the_category_and_remembers_it(anna_and_bo):
    anna, _ = anna_and_bo
    chips = ids_of(anna, "Chips")[0]
    assert db.update_history_categories(anna, {chips: "Snacks"}) == (1, 0)
    assert ids_and_categories(anna)[chips] == "Snacks"
    assert db.load_memory(anna) == {"Mjölk": "Dryck", "Chips": "Snacks"}


def test_other_purchases_keep_their_category(anna_and_bo):
    anna, _ = anna_and_bo
    before = ids_and_categories(anna)
    chips = ids_of(anna, "Chips")[0]
    db.update_history_categories(anna, {chips: "Snacks"})
    after = ids_and_categories(anna)
    assert {key: value for key, value in after.items() if key != chips} == {
        key: value for key, value in before.items() if key != chips
    }


def test_several_purchases_at_once(anna_and_bo):
    anna, _ = anna_and_bo
    first, second = ids_of(anna, "Mjölk")
    assert db.update_history_categories(anna, {first: "Mejeri", second: "Mejeri"}) == (2, 0)
    assert db.load_memory(anna)["Mjölk"] == "Mejeri"


def test_another_users_purchase_is_never_changed(anna_and_bo):
    anna, bo = anna_and_bo
    bos_milk = ids_of(bo, "Mjölk")[0]
    assert db.update_history_categories(anna, {bos_milk: "Mejeri"}) == (0, 1)
    assert ids_and_categories(bo)[bos_milk] == "Dryck"
    assert db.load_memory(bo) == {"Mjölk": "Dryck"}
    assert db.load_memory(anna) == {"Mjölk": "Dryck", "Chips": "Mejeri"}  # nothing remembered


def test_unknown_id_changes_nothing(anna_and_bo):
    anna, _ = anna_and_bo
    before = ids_and_categories(anna)
    assert db.update_history_categories(anna, {999_999: "Snacks"}) == (0, 1)
    assert ids_and_categories(anna) == before


def test_a_category_the_user_does_not_have_becomes_the_fallback(anna_and_bo):
    anna, bo = anna_and_bo
    db.add_category(bo, "Bos egen")
    chips = ids_of(anna, "Chips")[0]
    assert db.update_history_categories(anna, {chips: "Bos egen"}) == (1, 0)
    assert ids_and_categories(anna)[chips] == FALLBACK_CATEGORY
    assert db.load_memory(anna)["Chips"] == FALLBACK_CATEGORY  # chosen, so remembered


def test_the_same_category_again_counts_as_no_change_but_is_remembered(anna_and_bo):
    anna, _ = anna_and_bo
    db.save_memory(anna, {"Chips": "Snacks"})  # memory and history disagree
    chips = ids_of(anna, "Chips")[0]
    assert db.update_history_categories(anna, {chips: "Mejeri"}) == (0, 0)
    assert db.load_memory(anna)["Chips"] == "Mejeri"


def test_nothing_changes_when_the_memory_write_fails(anna_and_bo, monkeypatch):
    anna, _ = anna_and_bo
    before = ids_and_categories(anna)

    def locked(*_args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "_write_memory", locked)
    with pytest.raises(sqlite3.OperationalError):
        db.update_history_categories(anna, {ids_of(anna, "Chips")[0]: "Snacks"})
    assert ids_and_categories(anna) == before
    assert db.load_memory(anna) == {"Mjölk": "Dryck", "Chips": "Mejeri"}
