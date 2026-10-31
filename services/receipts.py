"""Receipt flows that combine core logic with the database.

No Streamlit here: the UI calls these functions and decides how to show the
result. Errors are passed on unchanged for the UI to handle:
- core.parser.NotAPdfError / ReceiptReadError when a PDF cannot be read
- InvalidReceipt when a receipt fails validation
- sqlite3.Error when the database fails
"""

from datetime import date
from typing import NamedTuple

import pandas as pd

from core.parser import read_receipt
from core.receipt import categorize, memory_from_receipt, validate_receipt
from integrations import db


class ImportResult(NamedTuple):
    """Outcome of importing a receipt PDF."""

    items: pd.DataFrame  # columns Item, Price, Category (empty if nothing was found)
    remembered: int  # how many items got their category from the user's memory
    purchase_date: date | None  # date printed on the receipt, None if not found


class InvalidReceipt(ValueError):
    """Raised when a receipt cannot be saved; `problems` lists why, per row."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def import_receipt(user_id, pdf_bytes, categories):
    """Read an ICA receipt PDF and pre-fill categories from the user's memory.

    `categories` are the user's current category names; remembered categories
    the user no longer has fall back to FALLBACK_CATEGORY.
    """
    parsed = read_receipt(pdf_bytes)
    if parsed.items.empty:
        return ImportResult(parsed.items, 0, parsed.purchase_date)
    categorized_items, remembered = categorize(parsed.items, db.load_memory(user_id), categories)
    return ImportResult(categorized_items, remembered, parsed.purchase_date)


def save_receipt(user_id, purchase_date, draft):
    """Validate the draft receipt, then save it to history and memory at once.

    Raises InvalidReceipt (nothing saved) if the draft has problems.
    Returns the number of history rows saved.
    """
    problems = validate_receipt(draft)
    if problems:
        raise InvalidReceipt(problems)
    return db.save_receipt(user_id, purchase_date, draft, memory_from_receipt(draft))
