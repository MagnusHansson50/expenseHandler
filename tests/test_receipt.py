import pandas as pd

from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_PRICE, RECEIPT_COLUMNS
from core.receipt import (
    Problem,
    add_rows,
    apply_editor_changes,
    categorize,
    empty_receipt,
    memory_from_receipt,
    normalize_receipt,
    validate_receipt,
)


def receipt(*rows):
    return normalize_receipt(pd.DataFrame(rows, columns=RECEIPT_COLUMNS))


# --- Shape ---------------------------------------------------------------


def test_empty_receipt_has_columns_and_dtypes():
    df = empty_receipt()
    assert df.empty
    assert list(df.columns) == RECEIPT_COLUMNS
    assert str(df["Price"].dtype) == "float64"


def test_normalize_adds_missing_columns_and_resets_index():
    df = normalize_receipt(pd.DataFrame({"Item": ["Milk"], "Price": [15]}, index=[7]))
    assert list(df.columns) == RECEIPT_COLUMNS
    assert df.index.tolist() == [0]
    assert df["Price"].tolist() == [15.0]
    assert df["Category"].isna().all()


def test_add_rows_to_empty_and_existing_receipt():
    first = add_rows(empty_receipt(), receipt(("Milk", 15.0, "Dairy")))
    both = add_rows(first, receipt(("Coffee", 45.0, "Drinks")))
    assert both["Item"].tolist() == ["Milk", "Coffee"]
    assert both.index.tolist() == [0, 1]


# --- Editor changes ------------------------------------------------------


def test_apply_editor_changes_edit_delete_and_add():
    df = receipt(("Milk", 15.0, "Other"), ("Chips", 31.0, "Other"), ("Bread", 42.0, "Bread"))
    changes = {
        "edited_rows": {"0": {"Category": "Dairy"}, 2: {"Price": 40.0}},
        "deleted_rows": [1],
        "added_rows": [{"Item": "Coffee", "Price": 45.0, "Category": "Drinks"}],
    }
    result = apply_editor_changes(df, changes)
    assert result.to_dict("records") == [
        {"Item": "Milk", "Price": 15.0, "Category": "Dairy"},
        {"Item": "Bread", "Price": 40.0, "Category": "Bread"},
        {"Item": "Coffee", "Price": 45.0, "Category": "Drinks"},
    ]
    assert result.index.tolist() == [0, 1, 2]


def test_apply_editor_changes_does_not_mutate_input():
    df = receipt(("Milk", 15.0, "Other"))
    apply_editor_changes(df, {"edited_rows": {0: {"Category": "Dairy"}}, "deleted_rows": [], "added_rows": []})
    assert df["Category"].tolist() == ["Other"]


def test_apply_editor_changes_with_partial_added_row():
    result = apply_editor_changes(receipt(), {"added_rows": [{"Item": "Gum"}]})
    assert result["Item"].tolist() == ["Gum"]
    assert result["Price"].isna().all()


# --- Categorize from memory ----------------------------------------------


def test_categorize_uses_memory_and_falls_back():
    items = pd.DataFrame({"Item": ["Milk", "Chips", "Unknown"], "Price": [15.0, 31.0, 9.0]})
    memory = {"Milk": "Dairy", "Chips": "Snacks"}
    result, remembered = categorize(items, memory, ["Dairy", "Snacks", FALLBACK_CATEGORY])
    assert result["Category"].tolist() == ["Dairy", "Snacks", FALLBACK_CATEGORY]
    assert remembered == 2
    assert "Category" not in items.columns  # input left untouched


def test_categorize_ignores_remembered_category_that_was_removed():
    items = pd.DataFrame({"Item": ["Candy bar"], "Price": [12.0]})
    result, remembered = categorize(items, {"Candy bar": "Candy"}, ["Snacks", FALLBACK_CATEGORY])
    assert result["Category"].tolist() == [FALLBACK_CATEGORY]
    assert remembered == 0


# --- Memory to learn -----------------------------------------------------


def test_memory_from_receipt_skips_blanks_and_last_row_wins():
    df = receipt(
        ("Milk", 15.0, "Dairy"),
        (" Coffee ", 45.0, "Drinks"),
        ("", 1.0, "Other"),
        ("No category", 2.0, None),
        ("Milk", 15.0, "Drinks"),
    )
    assert memory_from_receipt(df) == {"Milk": "Drinks", "Coffee": "Drinks"}


# --- Validation before saving --------------------------------------------


def test_valid_receipt_has_no_problems():
    df = receipt(
        ("Milk", 15.0, "Dairy"),
        ("x" * MAX_ITEM_LENGTH, MAX_PRICE, "Other"),
        ("Refund", -MAX_PRICE, "Other"),
        (None, None, None),  # empty row is ignored
    )
    assert validate_receipt(df) == []


def test_validate_receipt_reports_each_problem_with_row_number():
    df = receipt(
        ("Milk", 15.0, "Dairy"),
        ("x" * (MAX_ITEM_LENGTH + 1), 1.0, "Other"),
        ("Too expensive", MAX_PRICE + 1, "Other"),
        ("", 5.0, "Other"),
        ("No price", None, "Other"),
    )
    assert validate_receipt(df) == [
        Problem("problem_item_too_long", {"row": 2, "max": MAX_ITEM_LENGTH}),
        Problem("problem_price_out_of_range", {"row": 3, "max": MAX_PRICE}),
        Problem("problem_item_missing", {"row": 4}),
        Problem("problem_price_missing", {"row": 5}),
    ]


# --- Category labels in the editor ---------------------------------------

from core.receipt import changes_to_stored_categories, with_category_labels  # noqa: E402


def test_with_category_labels_translates_fallback_for_display_only():
    df = receipt(("Milk", 15.0, "Mejeri"), ("Gum", 9.0, FALLBACK_CATEGORY), ("New", 1.0, None))
    shown = with_category_labels(df, "sv")
    assert shown["Category"].tolist()[:2] == ["Mejeri", "Övrigt"]
    assert pd.isna(shown["Category"].tolist()[2])
    assert df["Category"].tolist()[1] == FALLBACK_CATEGORY  # original untouched


def test_changes_to_stored_categories_maps_labels_back():
    changes = {
        "edited_rows": {0: {"Category": "Övrigt"}, 1: {"Price": 5.0}, 2: {"Category": "Mejeri"}},
        "deleted_rows": [3],
        "added_rows": [{"Item": "Gum", "Category": "Övrigt"}, {"Item": "Bread"}],
    }
    stored = changes_to_stored_categories(changes, "sv")
    assert stored["edited_rows"] == {0: {"Category": FALLBACK_CATEGORY}, 1: {"Price": 5.0}, 2: {"Category": "Mejeri"}}
    assert stored["added_rows"] == [{"Item": "Gum", "Category": FALLBACK_CATEGORY}, {"Item": "Bread"}]
    assert stored["deleted_rows"] == [3]
    assert changes["edited_rows"][0] == {"Category": "Övrigt"}  # input untouched


def test_edit_in_swedish_editor_is_stored_with_internal_name():
    df = receipt(("Gum", 9.0, "Mejeri"))
    changes = changes_to_stored_categories({"edited_rows": {0: {"Category": "Övrigt"}}}, "sv")
    assert apply_editor_changes(df, changes)["Category"].tolist() == [FALLBACK_CATEGORY]
