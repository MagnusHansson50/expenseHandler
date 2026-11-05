"""core/backup.py: the backup file, the CSV export and what an import adds."""

import json
from datetime import date

import pandas as pd
import pytest

from core.backup import (
    BACKUP_FORMAT,
    MAX_BACKUP_BYTES,
    InvalidBackup,
    history_csv,
    make_backup,
    new_categories,
    new_history_rows,
    new_memory,
    read_backup,
)
from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_NAME_LENGTH, MAX_PRICE


def history(*rows):
    """Rows as db.get_history returns them (Id, Date, Item, Price, Category)."""
    return pd.DataFrame(
        [(number, *row) for number, row in enumerate(rows, 1)],
        columns=["Id", "Date", "Item", "Price", "Category"],
    )


SAMPLE = history(
    ("2026-10-20", "Mjölk 3%", 25.0, "Mejeri"),
    ("2026-10-20", "Kaffe", 59.9, FALLBACK_CATEGORY),
    ("2026-10-20", "Kaffe", 59.9, FALLBACK_CATEGORY),
    ("2026-10-21", "Rabatt", -6.8, "Mejeri"),
)


def backup_bytes(**changes):
    content = json.loads(make_backup(["Mejeri", FALLBACK_CATEGORY], {"Mjölk 3%": "Mejeri"}, SAMPLE, date(2026, 11, 5)))
    content.update(changes)
    return json.dumps(content).encode("utf-8")


def problem_keys(data):
    with pytest.raises(InvalidBackup) as caught:
        read_backup(data)
    return [(problem.key, problem.params) for problem in caught.value.problems]


# --- Writing and reading back ------------------------------------------------


def test_a_backup_reads_back_to_the_same_data():
    data = make_backup(["Mejeri", FALLBACK_CATEGORY], {"Mjölk 3%": "Mejeri"}, SAMPLE, date(2026, 11, 5))
    backup = read_backup(data)
    assert backup.categories == ["Mejeri", FALLBACK_CATEGORY]  # sorted in the file
    assert backup.memory == {"Mjölk 3%": "Mejeri"}
    assert backup.history.to_dict("records") == [
        {"Date": "2026-10-20", "Item": "Mjölk 3%", "Price": 25.0, "Category": "Mejeri"},
        {"Date": "2026-10-20", "Item": "Kaffe", "Price": 59.9, "Category": FALLBACK_CATEGORY},
        {"Date": "2026-10-20", "Item": "Kaffe", "Price": 59.9, "Category": FALLBACK_CATEGORY},
        {"Date": "2026-10-21", "Item": "Rabatt", "Price": -6.8, "Category": "Mejeri"},
    ]


def test_the_file_is_readable_json_with_format_version_and_no_passwords():
    content = json.loads(make_backup(["Mejeri"], {}, SAMPLE, date(2026, 11, 5)).decode("utf-8"))
    assert content["format"] == BACKUP_FORMAT
    assert content["version"] == 1
    assert content["exported"] == "2026-11-05"
    assert set(content) == {"format", "version", "exported", "categories", "memory", "history"}
    assert "Mjölk" in make_backup([], {}, SAMPLE, date(2026, 11, 5)).decode("utf-8")  # not \\u-escaped


def test_an_empty_account_makes_an_empty_backup():
    empty = history()
    backup = read_backup(make_backup([FALLBACK_CATEGORY], {}, empty, date(2026, 11, 5)))
    assert backup.categories == [FALLBACK_CATEGORY]
    assert backup.history.empty


# --- Refusing bad files ------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [b"", b"not json", b"\xff\xfe\x00", b"[1, 2]", b'{"format": "something-else", "version": 1}',
     b'{"format": "expensehandler-backup"}', b'{"format": "expensehandler-backup", "version": true}',
     b'{"format": "expensehandler-backup", "version": 1, "history": {}}', b"[" * 100_000],
)
def test_files_that_are_not_backups_are_unreadable(data):
    assert problem_keys(data) == [("backup_unreadable", {})]


def test_a_file_that_is_too_large_is_refused_before_reading():
    assert problem_keys(b" " * (MAX_BACKUP_BYTES + 1)) == [("backup_too_large", {"max": 5})]


def test_a_backup_from_a_newer_version_is_refused():
    assert problem_keys(backup_bytes(version=2)) == [("backup_too_new", {"version": 2, "supported": 1})]


@pytest.mark.parametrize("name", ["", "   ", "x" * (MAX_NAME_LENGTH + 1), "Övrigt", "övrigt", "OTHER ", 7])
def test_bad_category_names_are_reported(name):
    keys = problem_keys(backup_bytes(categories=["Mejeri", name]))
    assert [key for key, _ in keys] == ["backup_bad_category"]


def test_the_fallback_category_itself_is_allowed():
    assert FALLBACK_CATEGORY in read_backup(backup_bytes(categories=[FALLBACK_CATEGORY])).categories


@pytest.mark.parametrize("memory", [{"": "Mejeri"}, {"x" * (MAX_ITEM_LENGTH + 1): "Mejeri"}, {"Mjölk": 3}, {"Mjölk": ""}])
def test_bad_memory_entries_are_reported(memory):
    assert [key for key, _ in problem_keys(backup_bytes(memory=memory))] == ["backup_bad_memory"]


def entry(**changes):
    return {"date": "2026-10-20", "item": "Kaffe", "price": 59.9, "category": "Mejeri", **changes}


@pytest.mark.parametrize(
    "bad",
    [entry(price="59,90"), entry(price=True), entry(item=None), entry(date=20261020),
     entry(category=None), entry(category="x" * (MAX_NAME_LENGTH + 1)), {"date": "2026-10-20"},
     {**entry(), "password": "x"}, "Kaffe"],
)
def test_malformed_purchases_are_reported_with_their_row(bad):
    assert problem_keys(backup_bytes(history=[entry(), bad])) == [("backup_bad_entry", {"row": 2})]


@pytest.mark.parametrize("value", ["2026-13-01", "20261020", "2026-10-20T10:00", "igår"])
def test_invalid_dates_are_reported(value):
    assert problem_keys(backup_bytes(history=[entry(date=value)])) == [("backup_bad_date", {"row": 1})]


def test_item_and_price_limits_are_the_same_as_for_a_receipt():
    rows = [entry(item=" "), entry(item="x" * (MAX_ITEM_LENGTH + 1)), entry(price=MAX_PRICE + 1)]
    assert problem_keys(backup_bytes(history=rows)) == [
        ("problem_item_missing", {"row": 1}),
        ("problem_item_too_long", {"row": 2, "max": MAX_ITEM_LENGTH}),
        ("problem_price_out_of_range", {"row": 3, "max": MAX_PRICE}),
    ]


def test_every_problem_is_reported_at_once():
    keys = problem_keys(backup_bytes(categories=[""], memory={"": "x"}, history=[entry(date="x"), "y"]))
    assert [key for key, _ in keys] == ["backup_bad_category", "backup_bad_memory", "backup_bad_date", "backup_bad_entry"]


# --- CSV -----------------------------------------------------------------------


def test_swedish_csv_uses_semicolons_decimal_commas_labels_and_a_bom():
    text = history_csv(SAMPLE, "sv").decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").splitlines()
    assert lines[0] == "Datum;Vara;Pris (kr);Kategori"
    assert lines[1] == "2026-10-20;Mjölk 3%;25,00;Mejeri"
    assert lines[2] == "2026-10-20;Kaffe;59,90;Övrigt"
    assert lines[4] == "2026-10-21;Rabatt;-6,80;Mejeri"  # a negative price stays a number


def test_english_csv_uses_commas_and_decimal_points():
    lines = history_csv(SAMPLE, "en").decode("utf-8").lstrip("﻿").splitlines()
    assert lines[0] == "Date,Item,Price (kr),Category"
    assert lines[2] == "2026-10-20,Kaffe,59.90,Other"


def test_text_that_would_run_as_a_formula_is_defused():
    rows = history(("2026-10-20", "=HYPERLINK(\"http://example.com\")", 1.0, "+Kat"), ("2026-10-20", "@SUM", 1.0, "-x"))
    lines = history_csv(rows, "en").decode("utf-8").lstrip("﻿").splitlines()
    assert lines[1] == "2026-10-20,\"'=HYPERLINK(\"\"http://example.com\"\")\",1.00,'+Kat"
    assert lines[2] == "2026-10-20,'@SUM,1.00,'-x"


# --- What an import adds -------------------------------------------------------


def test_only_missing_categories_are_added():
    assert new_categories(["Mejeri", FALLBACK_CATEGORY], ["Frukt", "Mejeri", "Bröd"]) == ["Frukt", "Bröd"]


def test_the_users_own_remembered_choices_win():
    existing = {"Mjölk": "Dryck"}
    assert new_memory(existing, {"Mjölk": "Mejeri", "Bröd": "Bröd"}) == {"Bröd": "Bröd"}


def test_history_rows_already_present_are_not_added_again():
    backup = read_backup(make_backup([], {}, SAMPLE, date(2026, 11, 5))).history
    assert new_history_rows(history(), backup).shape[0] == 4
    assert new_history_rows(SAMPLE, backup).empty  # importing the same file again adds nothing


def test_identical_purchases_are_counted_not_merged():
    backup = read_backup(make_backup([], {}, SAMPLE, date(2026, 11, 5))).history
    one_coffee = history(("2026-10-20", "Kaffe", 59.9, FALLBACK_CATEGORY))
    added = new_history_rows(one_coffee, backup)
    assert added["Item"].tolist() == ["Mjölk 3%", "Kaffe", "Rabatt"]  # the second coffee only
