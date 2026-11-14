"""services/backup.py and the database functions behind it, against a temporary database."""

import json
import sqlite3
from datetime import date

import pandas as pd
import pytest

from core.backup import InvalidBackup
from core.constants import FALLBACK_CATEGORY, RECEIPT_COLUMNS
from integrations import db
from services import backup


def receipt(*rows):
    return pd.DataFrame(rows, columns=RECEIPT_COLUMNS)


@pytest.fixture
def anna(temp_db):
    """Anna with two categories, a remembered choice and three purchases on two dates."""
    user_id = temp_db.create_user("Anna", ["Mejeri", "Dryck"])
    temp_db.save_receipt(
        user_id, date(2026, 10, 20),
        receipt(("Mjölk", 15.9, "Mejeri"), ("Kaffe", 59.9, FALLBACK_CATEGORY)), {"Mjölk": "Mejeri"},
    )
    temp_db.save_receipt(user_id, date(2026, 10, 21), receipt(("Juice", 25.0, "Dryck")), {})
    return user_id


def purchases(user_id):
    return [tuple(row) for row in db.get_all_history(user_id)[["Date", "Item", "Price", "Category"]].to_numpy()]


# --- Export ----------------------------------------------------------------------


def test_export_contains_only_that_users_data(anna, temp_db):
    bo = temp_db.create_user("Bo", ["Bos kategori"])
    temp_db.save_receipt(bo, date(2026, 10, 20), receipt(("Bos te", 30.0, "Bos kategori")), {"Bos te": "Bos kategori"})

    content = json.loads(backup.export_backup(anna, today=date(2026, 11, 5)))
    assert content["exported"] == "2026-11-05"
    assert set(content["categories"]) == {"Mejeri", "Dryck", FALLBACK_CATEGORY}
    assert content["memory"] == {"Mjölk": "Mejeri"}
    assert [entry["item"] for entry in content["history"]] == ["Mjölk", "Kaffe", "Juice"]
    assert "Bo" not in json.dumps(content)


def test_csv_export_has_all_purchases(anna):
    lines = backup.export_history_csv(anna, "sv").decode("utf-8").lstrip("﻿").splitlines()
    assert lines[1:] == [
        "2026-10-20;Mjölk;15,90;Mejeri", "2026-10-20;Kaffe;59,90;Övrigt", "2026-10-21;Juice;25,00;Dryck"
    ]


def test_all_history_is_oldest_first_and_only_that_users(anna, temp_db):
    bo = temp_db.create_user("Bo")
    temp_db.save_receipt(bo, date(2026, 1, 1), receipt(("Bos te", 30.0, FALLBACK_CATEGORY)), {})
    assert [row[1] for row in purchases(anna)] == ["Mjölk", "Kaffe", "Juice"]


# --- Import ----------------------------------------------------------------------


def test_moving_to_a_new_account_brings_everything_along(anna, temp_db):
    data = backup.export_backup(anna)
    new_anna = temp_db.create_user("Anna på ny dator", [])

    counts = backup.import_backup(new_anna, data)

    assert counts == db.ImportCounts(categories=2, memory=1, purchases=3)
    assert set(temp_db.get_categories(new_anna)) == {"Mejeri", "Dryck", FALLBACK_CATEGORY}
    assert temp_db.load_memory(new_anna) == {"Mjölk": "Mejeri"}
    assert purchases(new_anna) == purchases(anna)


def test_importing_the_same_file_again_adds_nothing(anna, temp_db):
    data = backup.export_backup(anna)
    assert backup.import_backup(anna, data) == db.ImportCounts(0, 0, 0)
    new_anna = temp_db.create_user("Ny", [])
    backup.import_backup(new_anna, data)
    assert backup.import_backup(new_anna, data) == db.ImportCounts(0, 0, 0)
    assert len(purchases(new_anna)) == 3


def test_import_merges_with_what_the_user_already_has(anna, temp_db):
    data = backup.export_backup(anna)
    other = temp_db.create_user("Annan", ["Mejeri"])
    temp_db.save_receipt(other, date(2026, 10, 20), receipt(("Mjölk", 15.9, "Mejeri")), {"Mjölk": "Mejeri"})

    counts = backup.import_backup(other, data)

    assert counts == db.ImportCounts(categories=1, memory=0, purchases=2)  # Dryck; own choice kept; Mjölk already there
    assert temp_db.load_memory(other) == {"Mjölk": "Mejeri"}
    assert sorted(row[1] for row in purchases(other)) == ["Juice", "Kaffe", "Mjölk"]


def test_import_only_changes_that_users_data(anna, temp_db):
    data = backup.export_backup(anna)
    bo = temp_db.create_user("Bo", [])
    bo_before = (temp_db.get_categories(bo), temp_db.load_memory(bo), purchases(bo))
    new_anna = temp_db.create_user("Ny", [])
    backup.import_backup(new_anna, data)
    assert (temp_db.get_categories(bo), temp_db.load_memory(bo), purchases(bo)) == bo_before


def test_a_bad_file_adds_nothing(anna, temp_db):
    content = json.loads(backup.export_backup(anna))
    content["history"].append({"date": "not a date", "item": "x", "price": 1, "category": "Mejeri"})
    new_anna = temp_db.create_user("Ny", [])

    with pytest.raises(InvalidBackup) as caught:
        backup.import_backup(new_anna, json.dumps(content).encode("utf-8"))
    assert [problem.key for problem in caught.value.problems] == ["backup_bad_date"]
    assert temp_db.get_categories(new_anna) == [FALLBACK_CATEGORY]
    assert purchases(new_anna) == []


def test_a_failure_while_writing_adds_nothing(anna, temp_db, monkeypatch):
    data = backup.export_backup(anna)
    new_anna = temp_db.create_user("Ny", [])

    real_write_history = db._write_history
    calls = []

    def fail_on_second_date(conn, user_id, purchase_date, items_df):
        calls.append(purchase_date)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk full")
        return real_write_history(conn, user_id, purchase_date, items_df)

    monkeypatch.setattr(db, "_write_history", fail_on_second_date)
    with pytest.raises(sqlite3.OperationalError):
        backup.import_backup(new_anna, data)
    assert temp_db.get_categories(new_anna) == [FALLBACK_CATEGORY]
    assert temp_db.load_memory(new_anna) == {}
    assert purchases(new_anna) == []


def test_a_purchase_in_an_unknown_category_is_kept_as_other(temp_db):
    user_id = temp_db.create_user("Anna", [])
    data = json.dumps({
        "format": "expensehandler-backup", "version": 1, "exported": "2026-11-05",
        "categories": [FALLBACK_CATEGORY], "memory": {"Mjölk": "Raderad"},
        "history": [{"date": "2026-10-20", "item": "Mjölk", "price": 15.9, "category": "Raderad"}],
    }).encode("utf-8")
    counts = backup.import_backup(user_id, data)
    assert counts == db.ImportCounts(categories=0, memory=0, purchases=1)
    assert purchases(user_id) == [("2026-10-20", "Mjölk", 15.9, FALLBACK_CATEGORY)]


def test_reserved_or_invalid_category_names_are_never_added(temp_db):
    user_id = temp_db.create_user("Anna", [])
    no_history = pd.DataFrame(columns=["Date", "Item", "Price", "Category"])
    counts = db.import_user_data(user_id, ["Övrigt", " ", "x" * 51, "Ny"], {}, no_history)
    assert counts.categories == 1
    assert sorted(temp_db.get_categories(user_id)) == ["Ny", FALLBACK_CATEGORY]


# --- The max amount setting ------------------------------------------------------


def test_the_chosen_max_amount_goes_with_the_backup(temp_db):
    import json

    anna, bo = temp_db.create_user("Anna"), temp_db.create_user("Bo")
    temp_db.set_max_price(anna, 250_000)
    data = backup.export_backup(anna)
    assert json.loads(data)["settings"] == {"max_price": 250_000}
    counts = backup.import_backup(bo, data)
    assert counts.max_price_set is True
    assert temp_db.get_max_price(bo) == 250_000


def test_a_default_max_amount_is_not_written_to_the_backup(temp_db):
    import json

    anna = temp_db.create_user("Anna")
    assert json.loads(backup.export_backup(anna))["settings"] == {}


def test_importing_never_overwrites_a_max_amount_the_user_chose(temp_db):
    anna, bo = temp_db.create_user("Anna"), temp_db.create_user("Bo")
    temp_db.set_max_price(anna, 250_000)
    temp_db.set_max_price(bo, 20_000)
    counts = backup.import_backup(bo, backup.export_backup(anna))
    assert counts.max_price_set is False
    assert temp_db.get_max_price(bo) == 20_000
