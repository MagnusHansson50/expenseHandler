import pandas as pd

from core.calculator import sum_by_category, total_cost


def purchases(*rows):
    return pd.DataFrame(rows, columns=["Item", "Price", "Category"])


def test_total_cost_of_empty_frame_is_zero():
    assert total_cost(purchases()) == 0.0


def test_total_cost_includes_discounts_and_avoids_float_noise():
    df = purchases(("Milk", 0.1, "Dairy"), ("Cheese", 0.2, "Dairy"), ("Refund", -5.0, "Other"))
    assert total_cost(df) == -4.7


def test_sum_by_category_of_empty_frame():
    result = sum_by_category(purchases())
    assert result.empty
    assert result.index.name == "Category"
    assert list(result.columns) == ["Price"]


def test_sum_by_category_groups_sorts_and_handles_missing_categories():
    df = purchases(
        ("Milk", 0.1, "Dairy"),
        ("Cheese", 0.2, "Dairy"),
        ("Chips", 31.18, "Snacks"),
        ("Refund", -5.0, "Snacks"),
        ("Mystery", 10, None),
        ("Blank", 2, ""),
    )
    result = sum_by_category(df)
    assert result.index.name == "Category"
    assert result.index.tolist() == ["Snacks", "Other", "Dairy"]
    assert result["Price"].tolist() == [26.18, 12.0, 0.3]


def test_history_shaped_frame_with_extra_columns():
    df = pd.DataFrame(
        {
            "Id": [1, 2],
            "Date": ["2026-10-01", "2026-10-02"],
            "Item": ["Milk", "Coffee"],
            "Price": [15.0, 45.0],
            "Category": ["Dairy", "Drinks"],
        }
    )
    assert total_cost(df) == 60.0
    assert sum_by_category(df).to_dict()["Price"] == {"Drinks": 45.0, "Dairy": 15.0}
