import sqlite3
from datetime import date

import pandas as pd
import pytest

from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_NAME_LENGTH, MAX_PRICE
from integrations import db


def receipt(*rows):
    """Build a receipt DataFrame from (item, price, category) tuples."""
    return pd.DataFrame(rows, columns=["Item", "Price", "Category"])


# --- Setup ---------------------------------------------------------------


def test_init_db_is_idempotent(temp_db):
    temp_db.init_db()
    temp_db.init_db()
    assert temp_db.get_users() == []


def test_transaction_commits_when_block_succeeds(temp_db):
    with temp_db.transaction() as conn:
        conn.execute("INSERT INTO users (name) VALUES ('Anna')")
    assert [name for _, name in temp_db.get_users()] == ["Anna"]


def test_transaction_rolls_back_everything_when_block_raises(temp_db):
    with pytest.raises(RuntimeError):
        with temp_db.transaction() as conn:
            conn.execute("INSERT INTO users (name) VALUES ('Anna')")
            conn.execute("INSERT INTO users (name) VALUES ('Bo')")
            raise RuntimeError("simulated failure after two writes")
    assert temp_db.get_users() == []


# --- Users ---------------------------------------------------------------


def test_create_user_trims_name_and_lists_sorted(temp_db):
    bo = temp_db.create_user(" Bo ")
    anna = temp_db.create_user("anna")
    assert temp_db.get_users() == [(anna, "anna"), (bo, "Bo")]
    assert temp_db.get_user(bo) == (bo, "Bo")


def test_get_user_returns_none_for_unknown_id(temp_db):
    assert temp_db.get_user(999) is None


@pytest.mark.parametrize("name", ["", "   "])
def test_create_user_rejects_empty_name(temp_db, name):
    with pytest.raises(ValueError):
        temp_db.create_user(name)


def test_create_user_rejects_duplicate_name(temp_db):
    temp_db.create_user("Anna")
    with pytest.raises(ValueError, match="already exists"):
        temp_db.create_user("Anna")


def test_new_user_gets_default_categories(temp_db):
    user = temp_db.create_user("Anna")
    assert sorted(temp_db.get_categories(user)) == sorted(db.DEFAULT_CATEGORIES)


# --- Categories ----------------------------------------------------------


def test_add_and_delete_category(two_users):
    anna, _ = two_users
    assert db.add_category(anna, " Candy ") is True
    assert "Candy" in db.get_categories(anna)
    assert db.add_category(anna, "Candy") is False
    assert db.add_category(anna, "  ") is False
    assert db.delete_category(anna, "Candy") is True
    assert db.delete_category(anna, "Candy") is False


def test_fallback_category_cannot_be_deleted(two_users):
    anna, _ = two_users
    assert db.delete_category(anna, FALLBACK_CATEGORY) is False
    assert FALLBACK_CATEGORY in db.get_categories(anna)


def test_deleting_category_forgets_its_memory_but_keeps_history(two_users):
    anna, _ = two_users
    db.save_memory(anna, {"Chips": "Snacks", "Popcorn": "Snacks", "Milk": "Dairy"})
    db.save_history(anna, "2026-10-01", receipt(("Chips", 31.0, "Snacks")))

    assert db.delete_category(anna, "Snacks") is True
    assert db.load_memory(anna) == {"Milk": "Dairy"}
    assert db.get_history(anna, "2026-10-01", "2026-10-01")["Category"].tolist() == ["Snacks"]


def test_deleting_missing_category_leaves_memory(two_users):
    anna, _ = two_users
    db.save_memory(anna, {"Chips": "Snacks"})
    assert db.delete_category(anna, "No such category") is False
    assert db.load_memory(anna) == {"Chips": "Snacks"}


# --- Memory --------------------------------------------------------------


def test_save_memory_overwrites_and_skips_blanks(two_users):
    anna, _ = two_users
    db.save_memory(anna, {"Milk": "Dairy"})
    db.save_memory(anna, {"Milk": "Drinks", "": "Other", "Bread": None})
    assert db.load_memory(anna) == {"Milk": "Drinks"}


# --- History -------------------------------------------------------------


def test_save_history_skips_rows_without_item_or_price(two_users):
    anna, _ = two_users
    rows = receipt(
        ("Milk", 15.9, "Dairy"),
        ("Discount", -5.0, "Other"),
        ("", 3.0, "Other"),
        (None, 4.0, "Other"),
        ("No price", None, "Other"),
    )
    assert db.save_history(anna, date(2026, 10, 1), rows) == 2


def test_get_history_is_inclusive_and_ordered(two_users):
    anna, _ = two_users
    db.save_history(anna, "2026-09-30", receipt(("Before", 1.0, "Other")))
    db.save_history(anna, "2026-10-01", receipt(("First", 2.0, "Other")))
    db.save_history(anna, date(2026, 10, 31), receipt(("Last", 3.0, "Other")))
    db.save_history(anna, "2026-11-01", receipt(("After", 4.0, "Other")))

    history = db.get_history(anna, date(2026, 10, 1), "2026-10-31")
    assert list(history.columns) == db.HISTORY_COLUMNS
    assert history["Item"].tolist() == ["First", "Last"]
    assert history["Date"].tolist() == ["2026-10-01", "2026-10-31"]


def test_history_dates_and_delete_date(two_users):
    anna, _ = two_users
    db.save_history(anna, "2026-09-26", receipt(("A", 1.0, "Other"), ("B", 2.0, "Other")))
    db.save_history(anna, "2026-10-20", receipt(("C", 3.0, "Other")))
    assert db.get_history_dates(anna) == ["2026-10-20", "2026-09-26"]

    assert db.delete_history_date(anna, date(2026, 9, 26)) == 2
    assert db.get_history_dates(anna) == ["2026-10-20"]


# --- Input limits --------------------------------------------------------


def test_user_name_length_limit(temp_db):
    assert temp_db.create_user("A" * MAX_NAME_LENGTH)
    with pytest.raises(ValueError, match="at most"):
        temp_db.create_user("B" * (MAX_NAME_LENGTH + 1))


def test_category_name_length_limit(two_users):
    anna, _ = two_users
    assert db.add_category(anna, "C" * MAX_NAME_LENGTH) is True
    assert db.add_category(anna, "D" * (MAX_NAME_LENGTH + 1)) is False
    assert "D" * (MAX_NAME_LENGTH + 1) not in db.get_categories(anna)


def test_save_memory_skips_long_items_and_unknown_categories(two_users):
    anna, _ = two_users
    db.save_memory(
        anna,
        {
            "Milk": "Dairy",
            "x" * (MAX_ITEM_LENGTH + 1): "Dairy",
            "Gum": "Not a category",
        },
    )
    assert db.load_memory(anna) == {"Milk": "Dairy"}


def test_save_history_maps_unknown_category_to_fallback(two_users):
    anna, _ = two_users
    db.save_history(anna, "2026-10-01", receipt(("Gum", 9.0, "Not a category"), ("Milk", 15.0, "Dairy")))
    history = db.get_history(anna, "2026-10-01", "2026-10-01")
    assert history["Category"].tolist() == [FALLBACK_CATEGORY, "Dairy"]


@pytest.mark.parametrize(
    "row",
    [
        ("x" * (MAX_ITEM_LENGTH + 1), 1.0, "Other"),
        ("Too expensive", MAX_PRICE + 0.01, "Other"),
        ("Too negative", -MAX_PRICE - 0.01, "Other"),
        ("Infinite", float("inf"), "Other"),
    ],
)
def test_save_history_rejects_out_of_range_rows_and_saves_nothing(two_users, row):
    anna, _ = two_users
    with pytest.raises(ValueError):
        db.save_history(anna, "2026-10-01", receipt(("Milk", 15.0, "Dairy"), row))
    assert db.get_history_dates(anna) == []


def test_save_history_accepts_limits_exactly(two_users):
    anna, _ = two_users
    rows = receipt(("x" * MAX_ITEM_LENGTH, MAX_PRICE, "Other"), ("Refund", -MAX_PRICE, "Other"))
    assert db.save_history(anna, "2026-10-01", rows) == 2


# --- Saving a receipt (history + memory together) ------------------------


def test_save_receipt_writes_history_and_memory(two_users):
    anna, _ = two_users
    rows = receipt(("Milk", 15.0, "Dairy"), ("Chips", 31.0, "Snacks"))
    saved = db.save_receipt(anna, "2026-10-01", rows, {"Milk": "Dairy", "Chips": "Snacks"})

    assert saved == 2
    assert db.get_history(anna, "2026-10-01", "2026-10-01")["Item"].tolist() == ["Milk", "Chips"]
    assert db.load_memory(anna) == {"Milk": "Dairy", "Chips": "Snacks"}


def test_save_receipt_saves_nothing_when_memory_write_fails(two_users, monkeypatch):
    anna, _ = two_users

    def locked(*_args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "_write_memory", locked)
    with pytest.raises(sqlite3.OperationalError):
        db.save_receipt(anna, "2026-10-01", receipt(("Milk", 15.0, "Dairy")), {"Milk": "Dairy"})

    assert db.get_history_dates(anna) == []
    assert db.load_memory(anna) == {}


def test_retrying_after_a_failed_save_does_not_duplicate(two_users, monkeypatch):
    anna, _ = two_users
    rows = receipt(("Coffee", 45.0, "Drinks"))
    real_write_memory = db._write_memory
    calls = {"count": 0}

    def fails_once(*args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_write_memory(*args)

    monkeypatch.setattr(db, "_write_memory", fails_once)
    with pytest.raises(sqlite3.OperationalError):
        db.save_receipt(anna, "2026-10-01", rows, {"Coffee": "Drinks"})
    db.save_receipt(anna, "2026-10-01", rows, {"Coffee": "Drinks"})

    assert len(db.get_history(anna, "2026-10-01", "2026-10-01")) == 1
    assert db.load_memory(anna) == {"Coffee": "Drinks"}


def test_save_receipt_with_invalid_row_saves_neither_history_nor_memory(two_users):
    anna, _ = two_users
    rows = receipt(("Milk", 15.0, "Dairy"), ("Too expensive", MAX_PRICE + 1, "Other"))
    with pytest.raises(ValueError):
        db.save_receipt(anna, "2026-10-01", rows, {"Milk": "Dairy"})

    assert db.get_history_dates(anna) == []
    assert db.load_memory(anna) == {}


# --- User isolation ------------------------------------------------------


def test_users_have_separate_categories(two_users):
    anna, bo = two_users
    db.add_category(anna, "Candy")
    assert "Candy" not in db.get_categories(bo)

    # Same name may exist for both users, and deleting one leaves the other.
    assert db.add_category(bo, "Candy") is True
    db.delete_category(anna, "Candy")
    assert "Candy" in db.get_categories(bo)

    db.delete_category(bo, "Dairy")
    assert "Dairy" in db.get_categories(anna)


def test_users_have_separate_memory(two_users):
    anna, bo = two_users
    db.save_memory(anna, {"Milk": "Dairy"})
    assert db.load_memory(bo) == {}

    db.save_memory(bo, {"Milk": "Drinks"})
    assert db.load_memory(anna) == {"Milk": "Dairy"}
    assert db.load_memory(bo) == {"Milk": "Drinks"}


def test_another_users_category_is_not_accepted(two_users):
    anna, bo = two_users
    db.add_category(bo, "Candy")
    db.save_memory(anna, {"Gum": "Candy"})
    db.save_history(anna, "2026-10-01", receipt(("Gum", 9.0, "Candy")))

    assert db.load_memory(anna) == {}
    assert db.get_history(anna, "2026-10-01", "2026-10-01")["Category"].tolist() == [FALLBACK_CATEGORY]


def test_save_receipt_only_affects_that_user(two_users):
    anna, bo = two_users
    db.save_memory(bo, {"Milk": "Drinks"})
    db.save_receipt(anna, "2026-10-01", receipt(("Milk", 15.0, "Dairy")), {"Milk": "Dairy"})

    assert db.get_history_dates(bo) == []
    assert db.load_memory(bo) == {"Milk": "Drinks"}


def test_deleting_category_only_affects_that_users_memory(two_users):
    anna, bo = two_users
    db.save_memory(anna, {"Chips": "Snacks"})
    db.save_memory(bo, {"Chips": "Snacks"})

    db.delete_category(anna, "Snacks")
    assert db.load_memory(anna) == {}
    assert db.load_memory(bo) == {"Chips": "Snacks"}
    assert "Snacks" in db.get_categories(bo)


def test_users_have_separate_history(two_users):
    anna, bo = two_users
    db.save_history(anna, "2026-10-01", receipt(("Anna's milk", 15.0, "Dairy")))
    db.save_history(bo, "2026-10-01", receipt(("Bo's coffee", 45.0, "Drinks")))

    assert db.get_history(anna, "2026-01-01", "2026-12-31")["Item"].tolist() == ["Anna's milk"]
    assert db.get_history(bo, "2026-01-01", "2026-12-31")["Item"].tolist() == ["Bo's coffee"]

    # Deleting Anna's receipt on a date leaves Bo's receipt on the same date.
    assert db.delete_history_date(anna, "2026-10-01") == 1
    assert db.get_history_dates(anna) == []
    assert db.get_history_dates(bo) == ["2026-10-01"]
