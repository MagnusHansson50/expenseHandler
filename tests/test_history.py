"""core/history.py: which saved purchases got another category in the history list."""

import pandas as pd

from core.constants import FALLBACK_CATEGORY
from core.history import category_changes, filter_by_categories, filter_categories

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


# --- Filtering on categories --------------------------------------------------


def test_nothing_chosen_shows_every_purchase():
    assert filter_by_categories(HISTORY, []) is HISTORY


def test_only_the_chosen_categories_are_kept():
    shown = filter_by_categories(HISTORY, ["Dryck"])
    assert shown["Id"].tolist() == [7, 12]


def test_several_categories_can_be_chosen():
    shown = filter_by_categories(HISTORY, ["Dryck", FALLBACK_CATEGORY])
    assert shown["Id"].tolist() == [7, 9, 12]


def test_a_category_without_purchases_gives_an_empty_list():
    shown = filter_by_categories(HISTORY, ["Mejeri"])
    assert shown.empty
    assert list(shown.columns) == list(HISTORY.columns)


def test_the_filtered_rows_are_numbered_from_zero():
    # The history list maps editor rows by position: row 0 must be the first purchase shown.
    shown = filter_by_categories(HISTORY, ["Dryck"])
    assert shown.index.tolist() == [0, 1]
    assert category_changes(shown, edited(r1={"Category": "Mejeri"}), "sv") == {12: "Mejeri"}


def test_the_filter_does_not_change_the_history():
    before = HISTORY.copy()
    filter_by_categories(HISTORY, ["Dryck"])
    pd.testing.assert_frame_equal(HISTORY, before)


def test_the_users_categories_come_first_in_their_order():
    assert filter_categories(["Mejeri", "Dryck", FALLBACK_CATEGORY], HISTORY) == ["Mejeri", "Dryck", FALLBACK_CATEGORY]


def test_removed_categories_still_in_the_history_can_be_chosen():
    history = HISTORY.assign(Category=["Godis", "snacks", "Dryck"])
    assert filter_categories(["Dryck", FALLBACK_CATEGORY], history) == ["Dryck", FALLBACK_CATEGORY, "Godis", "snacks"]


def test_no_category_is_listed_twice():
    assert filter_categories(["Dryck", "Dryck"], HISTORY) == ["Dryck", FALLBACK_CATEGORY]


def test_without_purchases_the_users_categories_are_listed():
    assert filter_categories(["Dryck"], HISTORY.iloc[0:0]) == ["Dryck"]
