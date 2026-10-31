"""Business logic for the receipt being edited.

Pure functions on Pandas DataFrames with the columns in RECEIPT_COLUMNS.
No Streamlit and no database access: the UI passes in what it has loaded.
"""

import pandas as pd

from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_PRICE, RECEIPT_COLUMNS


def normalize_receipt(df):
    """Give the receipt the expected columns, a clean index and stable dtypes."""
    df = df.reindex(columns=RECEIPT_COLUMNS).reset_index(drop=True)
    return df.astype({"Item": "object", "Price": "float64", "Category": "object"})


def empty_receipt():
    return normalize_receipt(pd.DataFrame(columns=RECEIPT_COLUMNS))


def add_rows(receipt, rows):
    """Append rows to the receipt."""
    if receipt.empty:
        return normalize_receipt(rows)
    return normalize_receipt(pd.concat([receipt, rows], ignore_index=True))


def apply_editor_changes(receipt, changes):
    """Apply the change set reported by `st.data_editor` to the receipt.

    `changes` has the keys edited_rows ({row: {column: value}}), deleted_rows
    ([row, ...]) and added_rows ([{column: value}, ...]); row numbers refer to
    the receipt as it was given to the editor.
    """
    df = normalize_receipt(receipt)

    for row, values in changes.get("edited_rows", {}).items():
        for column, value in values.items():
            df.at[int(row), column] = value
    df = df.drop(index=[int(row) for row in changes.get("deleted_rows", [])])

    added = changes.get("added_rows", [])
    if added:
        df = pd.concat([df, pd.DataFrame(added, columns=RECEIPT_COLUMNS)], ignore_index=True)

    return normalize_receipt(df)


def categorize(items, memory, categories):
    """Give parsed items a Category from the user's memory.

    Items that are not remembered, or whose remembered category is no longer
    one of the user's categories, get FALLBACK_CATEGORY.
    Returns (items with a Category column, number categorized from memory).
    """
    valid = {item: category for item, category in memory.items() if category in categories}
    remembered = items["Item"].map(valid)
    categorized = items.assign(Category=remembered.fillna(FALLBACK_CATEGORY))
    return categorized, int(remembered.notna().sum())


def validate_receipt(receipt):
    """Return a list of problems that stop the receipt from being saved.

    Rows are numbered from 1 as shown to the user. An empty list means the
    receipt can be saved. Rows with neither item nor price are ignored, as
    they are when saving.
    """
    problems = []
    for number, row in enumerate(receipt.itertuples(index=False), 1):
        has_item = pd.notna(row.Item) and str(row.Item).strip() != ""
        has_price = pd.notna(row.Price)
        if not has_item and not has_price:
            continue
        if not has_item:
            problems.append(f"Row {number}: the item description is missing.")
        elif len(str(row.Item).strip()) > MAX_ITEM_LENGTH:
            problems.append(f"Row {number}: the item description is longer than {MAX_ITEM_LENGTH} characters.")
        if not has_price:
            problems.append(f"Row {number}: the price is missing.")
        elif not -MAX_PRICE <= float(row.Price) <= MAX_PRICE:
            problems.append(f"Row {number}: the price must be between -{MAX_PRICE} and {MAX_PRICE} kr.")
    return problems


def memory_from_receipt(receipt):
    """Return the item -> category choices to remember when a receipt is saved.

    If an item appears more than once, the last row wins.
    """
    rows = receipt.dropna(subset=["Item", "Category"])
    return {
        str(item).strip(): category
        for item, category in zip(rows["Item"], rows["Category"])
        if str(item).strip() and str(category).strip()
    }
