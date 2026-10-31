import sqlite3
from datetime import date

import pandas as pd
import pytest

from core.constants import FALLBACK_CATEGORY, MAX_PRICE, RECEIPT_COLUMNS
from core.parser import NotAPdfError, ReceiptReadError
from core.receipt import Problem
from integrations import db
from services import receipts
from test_parser import SAMPLE_RECEIPT, make_pdf


def draft(*rows):
    return pd.DataFrame(rows, columns=RECEIPT_COLUMNS)


# --- import_receipt ------------------------------------------------------


def test_import_receipt_parses_and_categorizes_from_memory(two_users):
    anna, _ = two_users
    db.save_memory(anna, {"Mjölk 3%": "Dairy"})

    result = receipts.import_receipt(anna, make_pdf(SAMPLE_RECEIPT), db.get_categories(anna))

    assert result.items["Item"].tolist() == ["Mjölk 3%", "Bananer Eko", "Super crunch prem", "Pant 1"]
    assert result.items["Category"].tolist() == ["Dairy"] + [FALLBACK_CATEGORY] * 3
    assert result.remembered == 1
    assert result.purchase_date == date(2026, 10, 20)


def test_import_receipt_uses_only_that_users_memory(two_users):
    anna, bo = two_users
    db.save_memory(bo, {"Mjölk 3%": "Drinks"})
    result = receipts.import_receipt(anna, make_pdf(SAMPLE_RECEIPT), db.get_categories(anna))
    assert result.remembered == 0


def test_import_receipt_without_items_does_not_touch_the_database(two_users, monkeypatch):
    anna, _ = two_users
    monkeypatch.setattr(db, "load_memory", lambda *_: pytest.fail("memory should not be loaded"))
    result = receipts.import_receipt(anna, make_pdf("Just a header\nNo items here"), [])
    assert result.items.empty
    assert result.remembered == 0


@pytest.mark.parametrize(
    "data, error",
    [(b"not a pdf", NotAPdfError), (b"%PDF-1.4\nbroken body", ReceiptReadError)],
)
def test_import_receipt_passes_read_errors_on(two_users, data, error):
    anna, _ = two_users
    with pytest.raises(error):
        receipts.import_receipt(anna, data, [])


def test_import_receipt_passes_database_errors_on(two_users, monkeypatch):
    anna, _ = two_users

    def locked(*_args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "load_memory", locked)
    with pytest.raises(sqlite3.OperationalError):
        receipts.import_receipt(anna, make_pdf(SAMPLE_RECEIPT), [])


# --- save_receipt --------------------------------------------------------


def test_save_receipt_saves_history_and_learns_memory(two_users):
    anna, _ = two_users
    saved = receipts.save_receipt(anna, date(2026, 10, 1), draft(("Milk", 15.0, "Dairy")))

    assert saved == 1
    assert db.get_history_dates(anna) == ["2026-10-01"]
    assert db.load_memory(anna) == {"Milk": "Dairy"}


def test_invalid_receipt_is_rejected_with_problems_and_nothing_saved(two_users):
    anna, _ = two_users
    with pytest.raises(receipts.InvalidReceipt) as caught:
        receipts.save_receipt(
            anna, date(2026, 10, 1), draft(("Milk", 15.0, "Dairy"), ("TV", MAX_PRICE + 1, "Other"))
        )

    assert caught.value.problems == [Problem("problem_price_out_of_range", {"row": 2, "max": MAX_PRICE})]
    assert db.get_history_dates(anna) == []
    assert db.load_memory(anna) == {}
