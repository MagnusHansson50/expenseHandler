"""Business logic for the receipt being edited.

Pure functions on Pandas DataFrames with the columns in RECEIPT_COLUMNS.
No Streamlit and no database access: the UI passes in what it has loaded.
"""

from typing import NamedTuple

import pandas as pd

from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_PRICE, RECEIPT_COLUMNS
from core.i18n import category_label, category_value


class Problem(NamedTuple):
    """A reason a receipt cannot be saved, as a translation key plus its parameters.

    The UI shows it with t(problem.key, lang, **problem.params).
    """

    key: str
    params: dict


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


def with_category_labels(receipt, lang):
    """Copy of the receipt with categories as shown in `lang` (for display only)."""
    shown = receipt.copy()
    shown["Category"] = shown["Category"].map(
        lambda name: category_label(name, lang) if isinstance(name, str) else name
    )
    return shown


def changes_to_stored_categories(changes, lang):
    """Turn category labels in a `st.data_editor` change set back into stored names.

    The editor shows with_category_labels(), so a category picked there is a
    label (e.g. "Övrigt"); it must be saved as the stored name ("Other").
    """
    def stored(values):
        if isinstance(values.get("Category"), str):
            return {**values, "Category": category_value(values["Category"], lang)}
        return values

    return {
        **changes,
        "edited_rows": {row: stored(values) for row, values in changes.get("edited_rows", {}).items()},
        "added_rows": [stored(values) for values in changes.get("added_rows", [])],
    }


def categorize(items, memory, categories):
    """Give parsed items a Category from the user's memory.

    Items that are not remembered, or whose remembered category is no longer
    one of the user's categories, get FALLBACK_CATEGORY.
    Returns (items with a Category column, number categorized from memory).
    """
    valid = {item: category for item, category in memory.items() if category in categories}
    # astype(object): when nothing is remembered, map() returns float NaNs, and
    # pandas will stop allowing a string fill value for a float column.
    remembered = items["Item"].map(valid).astype(object)
    categorized = items.assign(Category=remembered.fillna(FALLBACK_CATEGORY))
    return categorized, int(remembered.notna().sum())


def uncategorized_items(receipt, memory, categories):
    """Return the names of items that still need a category, in receipt order, each once.

    An item needs one when its category is missing or no longer one of the
    user's `categories`, or when it is FALLBACK_CATEGORY although the user has
    not chosen that for the item before (`memory`): an item the user filed
    under FALLBACK_CATEGORY on purpose is not asked about again.
    """
    names = []
    for item, category in zip(receipt["Item"], receipt["Category"], strict=True):
        name = str(item).strip() if isinstance(item, str) else ""
        if not name or name in names:
            continue
        if category not in categories:
            names.append(name)
        elif category == FALLBACK_CATEGORY and memory.get(name) != FALLBACK_CATEGORY:
            names.append(name)
    return names


def _rows_named(df, item):
    return df["Item"].map(lambda name: isinstance(name, str) and name.strip() == item)


def set_item_category(receipt, item, category):
    """Give every row of the receipt named `item` the category `category`."""
    df = normalize_receipt(receipt)
    df.loc[_rows_named(df, item), "Category"] = category
    return df


def clear_category(receipt, category):
    """Put the receipt's rows in `category` back in FALLBACK_CATEGORY (after it was removed).

    Without this the table would still show the removed category while the
    rows already count as having none, and saving would file them under
    FALLBACK_CATEGORY anyway.
    """
    df = normalize_receipt(receipt)
    df.loc[df["Category"] == category, "Category"] = FALLBACK_CATEGORY
    return df


def remove_row(receipt, row):
    """Return the receipt without the row at position `row` (0-based, as shown); unchanged if there is none."""
    df = normalize_receipt(receipt)
    if not 0 <= row < len(df):
        return df
    return normalize_receipt(df.drop(index=row))


def item_rows(receipt, item):
    """Return the receipt's rows named `item`."""
    df = normalize_receipt(receipt)
    return normalize_receipt(df[_rows_named(df, item)])


def remove_item(receipt, item):
    """Return the receipt without any row named `item` (e.g. something bought for someone else)."""
    df = normalize_receipt(receipt)
    return normalize_receipt(df[~_rows_named(df, item)])


def item_total(receipt, item):
    """The summed price of every row of the receipt named `item`, rounded to öre."""
    return round(float(receipt.loc[_rows_named(receipt, item), "Price"].sum()), 2)


def validate_receipt(receipt):
    """Return a list of Problem that stop the receipt from being saved.

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
            problems.append(Problem("problem_item_missing", {"row": number}))
        elif len(str(row.Item).strip()) > MAX_ITEM_LENGTH:
            problems.append(Problem("problem_item_too_long", {"row": number, "max": MAX_ITEM_LENGTH}))
        if not has_price:
            problems.append(Problem("problem_price_missing", {"row": number}))
        elif not -MAX_PRICE <= float(row.Price) <= MAX_PRICE:
            problems.append(Problem("problem_price_out_of_range", {"row": number, "max": MAX_PRICE}))
    return problems


def memory_from_receipt(receipt, undecided=()):
    """Return the item -> category choices to remember when a receipt is saved.

    If an item appears more than once, the last row wins. Items in `undecided`
    (still without a real category, see uncategorized_items) are not
    remembered: remembering them as FALLBACK_CATEGORY would read as a choice
    and they would never be asked about again.
    """
    rows = receipt.dropna(subset=["Item", "Category"])
    return {
        str(item).strip(): category
        for item, category in zip(rows["Item"], rows["Category"], strict=True)
        if str(item).strip() and str(category).strip() and str(item).strip() not in undecided
    }
