"""A user's own data as files: a backup to read back in, and the history as CSV.

The backup is JSON with a format name and version, so later versions of the
app can still read old backups:

    {"format": "expensehandler-backup", "version": 1, "exported": "2026-11-05",
     "categories": ["Mejeri", "Other"],
     "memory": {"Mjölk 3%": "Mejeri"},
     "history": [{"date": "2026-10-20", "item": "Mjölk 3%", "price": 25.0, "category": "Mejeri"}]}

It never contains passwords. Categories are stored names (FALLBACK_CATEGORY as
"Other"), never labels. read_backup checks everything against the same limits
as the rest of the app and reports every problem at once; names in the
problems' params come from the file, so the UI escapes them before showing.

Importing merges: new_categories, new_memory and new_history_rows say what a
backup adds to what the user already has, so importing the same file twice
adds nothing the second time.
"""

import csv
import io
import json
import math
from collections import Counter
from datetime import date
from typing import NamedTuple

import pandas as pd

from core.constants import (
    FALLBACK_CATEGORY,
    FALLBACK_CATEGORY_LABELS,
    MAX_ITEM_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PRICE_CEILING,
    MAX_PRICE_SETTING_MIN,
    MAX_UPLOAD_MB,
)
from core.i18n import category_label, resolve_language, t
from core.receipt import Problem, validate_receipt
from core.settings import max_price_problem

BACKUP_FORMAT = "expensehandler-backup"
BACKUP_VERSION = 2  # 2 added "settings" (max_price); version 1 files are still read
MAX_BACKUP_BYTES = MAX_UPLOAD_MB * 1024 * 1024  # a larger file could not be uploaded anyway
HISTORY_FIELDS = ("date", "item", "price", "category")
BACKUP_HISTORY_COLUMNS = ["Date", "Item", "Price", "Category"]

# Text cells starting with these are run as formulas by spreadsheet programs
# ("CSV injection"); such cells get a leading apostrophe in the CSV export.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


class Backup(NamedTuple):
    """What a backup file holds."""

    categories: list  # stored category names
    memory: dict  # item -> stored category name
    history: pd.DataFrame  # columns Date (YYYY-MM-DD text), Item, Price, Category
    max_price: float | None = None  # the highest price per item chosen, None if not in the file


class InvalidBackup(ValueError):
    """The file cannot be imported; `problems` lists why (Problem), nothing was read."""

    def __init__(self, problems):
        super().__init__("; ".join(problem.key for problem in problems))
        self.problems = problems


# --- Writing -----------------------------------------------------------------


def make_backup(categories, memory, history, exported_on, max_price=None):
    """The backup file (UTF-8 JSON bytes) for one user's categories, memory, history and settings.

    `max_price` is the highest price per item the user has chosen, or None if
    they kept the default; then the file has no setting for it.
    """
    content = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported": exported_on.isoformat(),
        "categories": sorted(categories),
        "memory": dict(sorted(memory.items())),
        "history": [
            {
                "date": str(row.Date),
                "item": row.Item,
                "price": round(float(row.Price), 2),
                "category": row.Category if isinstance(row.Category, str) else FALLBACK_CATEGORY,
            }
            for row in history.itertuples(index=False)
        ],
        "settings": {} if max_price is None else {"max_price": max_price},
    }
    return json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")


def history_csv(history, lang):
    """The history as CSV bytes that a spreadsheet program in `lang` opens directly.

    Swedish: semicolons and decimal commas; English: commas and decimal points.
    UTF-8 with a byte order mark so Excel shows å, ä and ö. Categories are shown
    as labels ("Övrigt"); text cells that would start a formula are defused.
    """
    swedish = resolve_language(lang) == "sv"
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";" if swedish else ",", lineterminator="\r\n")
    writer.writerow([t(key, lang) for key in ("col_date", "col_item", "col_price", "col_category")])
    for row in history.itertuples(index=False):
        price = f"{float(row.Price):.2f}"
        writer.writerow([
            str(row.Date),
            _defuse(row.Item),
            price.replace(".", ",") if swedish else price,
            _defuse(category_label(row.Category, lang)),
        ])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _defuse(text):
    text = "" if text is None else str(text)
    return "'" + text if text.startswith(FORMULA_STARTS) else text


def download_name(user_name, day, extension):
    """A file name such as "ExpenseHandler-Anna-2026-11-05.json" that is safe on every system.

    Letters (also å, ä, ö) and digits are kept; anything else in the user
    name, such as slashes, colons, quotes, wildcards or spaces, becomes "_".
    """
    safe = "".join(char if char.isalnum() else "_" for char in user_name.strip())[:MAX_NAME_LENGTH] or "user"
    return f"ExpenseHandler-{safe}-{day.isoformat()}.{extension}"


# --- Reading -----------------------------------------------------------------


def read_backup(data):
    """Read and check a backup file. Returns a Backup, or raises InvalidBackup."""
    if len(data) > MAX_BACKUP_BYTES:
        raise InvalidBackup([Problem("backup_too_large", {"max": MAX_UPLOAD_MB})])
    try:
        content = json.loads(data.decode("utf-8-sig"))
    # UnicodeDecodeError: not text; JSONDecodeError: not JSON; other ValueError: a number Python
    # will not convert (an integer of more than 4300 digits); RecursionError: nested too deep.
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise InvalidBackup([Problem("backup_unreadable", {})]) from None
    if not isinstance(content, dict) or content.get("format") != BACKUP_FORMAT:
        raise InvalidBackup([Problem("backup_unreadable", {})])
    version = content.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise InvalidBackup([Problem("backup_unreadable", {})])
    if version > BACKUP_VERSION:
        raise InvalidBackup([Problem("backup_too_new", {"version": version, "supported": BACKUP_VERSION})])

    categories = content.get("categories", [])
    memory = content.get("memory", {})
    entries = content.get("history", [])
    settings = content.get("settings", {})  # not in version 1 files
    if not all(isinstance(value, kind) for value, kind in
               ((categories, list), (memory, dict), (entries, list), (settings, dict))):
        raise InvalidBackup([Problem("backup_unreadable", {})])

    problems = []
    max_price = settings.get("max_price")
    if max_price is not None and max_price_problem(max_price):
        # One message for "not a number" and "out of range": both say what the value must be.
        problems.append(Problem("backup_bad_max_price", {"min": MAX_PRICE_SETTING_MIN, "max": MAX_PRICE_CEILING}))
    problems += _category_problems(categories)
    problems += _memory_problems(memory)
    rows, history_problems = _history_rows(entries)
    problems += history_problems
    if problems:
        raise InvalidBackup(problems)

    names = list(dict.fromkeys(name.strip() for name in categories))
    remembered = {item.strip(): category.strip() for item, category in memory.items()}
    return Backup(names, remembered, pd.DataFrame(rows, columns=BACKUP_HISTORY_COLUMNS), max_price)


def _category_problems(categories):
    reserved = {label.casefold() for label in FALLBACK_CATEGORY_LABELS.values()}
    problems = []
    for name in categories:
        if not isinstance(name, str) or not name.strip():
            problems.append(Problem("backup_category_empty", {}))
        elif len(name.strip()) > MAX_NAME_LENGTH:
            problems.append(Problem("backup_category_too_long", {"name": name.strip()[:MAX_NAME_LENGTH],
                                                                 "max": MAX_NAME_LENGTH}))
        elif name.strip() != FALLBACK_CATEGORY and name.strip().casefold() in reserved:
            problems.append(Problem("backup_category_reserved", {"name": name.strip()}))
    return problems


def _memory_problems(memory):
    problems = []
    for item, category in memory.items():
        if not item.strip() or len(item.strip()) > MAX_ITEM_LENGTH:
            problems.append(Problem("backup_memory_bad_item", {"item": item[:MAX_ITEM_LENGTH],
                                                               "max": MAX_ITEM_LENGTH}))
        elif not isinstance(category, str) or not category.strip() or len(category.strip()) > MAX_NAME_LENGTH:
            problems.append(Problem("backup_memory_bad_category", {"item": item.strip(), "max": MAX_NAME_LENGTH}))
    return problems


def _history_rows(entries):
    """Check the shape and values of each history entry; return (rows, problems)."""
    rows, problems = [], []
    for number, entry in enumerate(entries, 1):
        shape_problem = _entry_shape_problem(entry, number)
        if shape_problem:
            problems.append(shape_problem)
            rows.append({"Date": None, "Item": None, "Price": None, "Category": None})
            continue
        if not _is_iso_date(entry["date"]):
            problems.append(Problem("backup_bad_date", {"row": number}))
        rows.append({
            "Date": entry["date"],
            "Item": entry["item"].strip(),
            "Price": float(entry["price"]),
            "Category": entry["category"].strip() or FALLBACK_CATEGORY,
        })
    # Item and price limits as for a receipt, with the same row numbers. The
    # placeholder rows of malformed entries have neither, so they are skipped.
    # Prices are checked against the ceiling, not a user's own limit: these
    # purchases were saved before, perhaps under a higher limit.
    shaped = pd.DataFrame(rows, columns=BACKUP_HISTORY_COLUMNS)
    problems += validate_receipt(shaped[["Item", "Price", "Category"]], MAX_PRICE_CEILING)
    return rows, sorted(problems, key=lambda problem: problem.params["row"])


def _entry_shape_problem(entry, row):
    """What is wrong with the shape or value types of one history entry, or None.

    Checked in order, so the first thing wrong is reported: not an object,
    the wrong set of fields, then each field. The date's format and the
    item and price limits are checked afterwards (backup_bad_date, and
    validate_receipt as for a receipt).
    """
    if not isinstance(entry, dict):
        return Problem("backup_entry_not_purchase", {"row": row})
    if set(entry) != set(HISTORY_FIELDS):
        return Problem("backup_entry_fields", {"row": row})
    for field in ("date", "item", "category"):
        if not isinstance(entry[field], str):
            return Problem("backup_entry_not_text", {"row": row, "field": field})
    price = entry["price"]
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price):
        return Problem("backup_entry_bad_price", {"row": row})
    if len(entry["category"].strip()) > MAX_NAME_LENGTH:
        return Problem("backup_entry_category_too_long", {"row": row, "max": MAX_NAME_LENGTH})
    return None


def _is_iso_date(text):
    if len(text) != 10:
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


# --- Merging -----------------------------------------------------------------


def new_max_price(chosen, in_file):
    """The highest price per item to take from a backup, or None to keep the user's.

    Like remembered categories, the user's own choice wins: the file's value
    is only used when the user has not chosen one (`chosen` is None).
    """
    return in_file if chosen is None else None


def new_categories(existing, backup_categories):
    """Categories in the backup that the user does not have yet, in backup order."""
    return [name for name in backup_categories if name not in set(existing)]


def new_memory(existing, backup_memory):
    """Remembered choices for items the user has no choice for yet (the user's own choices win)."""
    return {item: category for item, category in backup_memory.items() if item not in existing}


def new_history_rows(existing, backup_history):
    """Rows of the backup that are not in the user's history yet.

    Rows are compared on date, item, price and category, and counted: a
    backup with two identical coffees on one day adds two, or one if the
    history already has one, or none if it has both. Importing the same file
    twice therefore adds nothing the second time.
    """
    have = Counter(_row_key(row) for row in existing.itertuples(index=False))
    keep = []
    for index, row in enumerate(backup_history.itertuples(index=False)):
        key = _row_key(row)
        if have[key]:
            have[key] -= 1
        else:
            keep.append(index)
    return backup_history.iloc[keep].reset_index(drop=True)


def _row_key(row):
    return (str(row.Date), str(row.Item).strip(), round(float(row.Price), 2), row.Category)
