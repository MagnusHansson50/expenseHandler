"""core/history.py: which saved purchases got another category in the history list."""

import pandas as pd

from core.constants import FALLBACK_CATEGORY
from core.history import category_changes

HISTORY = pd.DataFrame(
    [
        (7, "2026-11-01", "Mjölk", 15.9, "Dryck"),
        (9, "2026-11-01", "Chips", 25.0, FALLBACK_CATEGORY),
        (12, "2026-11-02", "Kaffe", 59.9, "Dryck"),
    ],
    columns=["Id", "Date", "Item", "Price", "Category"],
)


def edited(**rows):
    return {"edited_rows": {int(row[1:]): values for row, values in rows.items()}}


def test_rows_are_mapped_to_history_ids():
    assert category_changes(HISTORY, edited(r0={"Category": "Mejeri"}, r2={"Category": "Snacks"}), "sv") == {
        7: "Mejeri",
        12: "Snacks",
    }


def test_fallback_label_is_stored_as_other():
    assert category_changes(HISTORY, edited(r0={"Category": "Övrigt"}), "sv") == {7: FALLBACK_CATEGORY}
    assert category_changes(HISTORY, edited(r0={"Category": "Other"}), "en") == {7: FALLBACK_CATEGORY}


def test_unchanged_category_is_left_out():
    assert category_changes(HISTORY, edited(r0={"Category": "Dryck"}), "sv") == {}
    assert category_changes(HISTORY, edited(r1={"Category": "Övrigt"}), "sv") == {}  # shown label, same category


def test_cleared_category_is_left_out():
    assert category_changes(HISTORY, edited(r0={"Category": None}, r1={"Category": " "}), "sv") == {}


def test_other_columns_and_added_or_deleted_rows_are_ignored():
    changes = {
        "edited_rows": {0: {"Price": 1.0, "Item": "Ändrad"}},
        "added_rows": [{"Category": "Mejeri"}],
        "deleted_rows": [1],
    }
    assert category_changes(HISTORY, changes, "sv") == {}


def test_no_changes():
    assert category_changes(HISTORY, {}, "sv") == {}
