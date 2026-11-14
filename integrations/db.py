"""SQLite data layer for ExpenseHandler.

Every table except `users` is tied to a user, and every function that touches
those tables takes a `user_id` so one user's data can never leak into another's.
"""

import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from core.constants import (
    FALLBACK_CATEGORY,
    FALLBACK_CATEGORY_LABELS,
    MAX_ITEM_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PRICE,
    MAX_PRICE_CEILING,
    MAX_PRICE_SETTING_MIN,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "expenses.db"


def database_path(env=os.environ):
    """The database file: EXPENSES_DB_PATH if it is set, else expenses.db next to the code.

    EXPENSES_DB_PATH lets the desktop program, tests and local experiments use
    another file. An empty or blank value counts as not set, so it never
    becomes a file named " ".
    """
    configured = env.get("EXPENSES_DB_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_DB_PATH


DB_PATH = database_path()

DEFAULT_CATEGORIES = [
    "Dairy",
    "Pantry",
    "Fruit",
    "Vegetables",
    "Meat & Fish",
    "Bread",
    "Frozen",
    "Drinks",
    "Snacks",
    "Household",
    FALLBACK_CATEGORY,
]

HISTORY_COLUMNS = ["Id", "Date", "Item", "Price", "Category"]

_RESERVED_CATEGORY_NAMES = {
    label.casefold() for label in (FALLBACK_CATEGORY, *FALLBACK_CATEGORY_LABELS.values())
}


class User(NamedTuple):
    """A row from the users table."""

    id: int
    name: str


class UserNameError(ValueError):
    """A user name was rejected. `key` and `params` let the UI show it translated."""

    key = ""

    def __init__(self, message, **params):
        super().__init__(message)
        self.params = params


class UserNameEmpty(UserNameError):
    key = "user_name_empty"


class UserNameTooLong(UserNameError):
    key = "user_name_too_long"


class UserNameTaken(UserNameError):
    key = "user_name_taken"


class DatabaseTooNew(Exception):
    """The database was written by a newer version of the app; it is left untouched.

    `key` and `params` let the UI show it translated.
    """

    key = "database_too_new"

    def __init__(self, found, supported):
        super().__init__(f"Database schema version {found} is newer than this app supports ({supported}).")
        self.params = {"found": found, "supported": supported}


# The schema version, kept in the database file itself (PRAGMA user_version), so
# a database from an older version of the desktop program is upgraded and one
# from a newer version is refused instead of damaged. 0 means "before
# versioning": those files already have the version 1 tables.
# To change the schema: leave the CREATE TABLE script in init_db as version 1,
# add the change as _MIGRATIONS[n] (a function taking the open connection) and
# set SCHEMA_VERSION = n.
SCHEMA_VERSION = 2


def _add_settings_table(conn):
    """Version 2: one row of settings per user (only the highest price per item so far).

    A user without a row has the defaults (MAX_PRICE). The row goes with the
    user through ON DELETE CASCADE, like their other data.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            user_id   INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            max_price REAL NOT NULL
        )
        """
    )


_MIGRATIONS = {2: _add_settings_table}


def get_connection():
    """Open a new connection. Read-only callers close it via `closing(...)`."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction():
    """Run a block of writes as one unit of work.

    Yields a connection. If the block finishes, everything it wrote is
    committed; if it raises, everything is rolled back and the exception
    propagates. The connection is always closed afterwards.
    """
    conn = get_connection()
    try:
        with conn:  # sqlite3: commit on success, rollback on exception
            yield conn
    finally:
        conn.close()


def init_db():
    """Create the tables if needed and bring the schema up to SCHEMA_VERSION.

    Raises DatabaseTooNew, and changes nothing, if the file comes from a newer
    version of the app.
    """
    with transaction() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise DatabaseTooNew(version, SCHEMA_VERSION)
        # The version 1 schema; later changes are migrations (see SCHEMA_VERSION).
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS categories (
                name    TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, name)
            );

            CREATE TABLE IF NOT EXISTS memory (
                item     TEXT NOT NULL,
                category TEXT NOT NULL,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, item)
            );

            CREATE TABLE IF NOT EXISTS history (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                date     TEXT NOT NULL,
                item     TEXT NOT NULL,
                price    REAL NOT NULL,
                category TEXT,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_history_user_date ON history (user_id, date);

            CREATE TABLE IF NOT EXISTS credentials (
                user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                password_hash BLOB NOT NULL,
                salt          BLOB NOT NULL
            );
            """
        )
        conn.execute("BEGIN")  # executescript commits; the upgrade below is one transaction
        for target in range(max(version, 1) + 1, SCHEMA_VERSION + 1):
            _MIGRATIONS[target](conn)
        # PRAGMA takes no ? parameters. SCHEMA_VERSION is an int constant, never user input.
        conn.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")


def _to_iso(value):
    """Normalize a date or 'YYYY-MM-DD' string to an ISO date string."""
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


# --- Users ---------------------------------------------------------------


def create_user(name, default_categories=DEFAULT_CATEGORIES):
    """Create a user, seed their starting categories and return the new id.

    `default_categories` are the names to start with, e.g. in the language
    selected in the UI (core.i18n.DEFAULT_CATEGORIES); FALLBACK_CATEGORY is
    always added. Raises UserNameEmpty, UserNameTooLong or UserNameTaken (all
    UserNameError, a ValueError) if the name is rejected.
    """
    with transaction() as conn:
        return _insert_user(conn, name, default_categories)


def create_user_with_password(name, password_hash, salt, default_categories=DEFAULT_CATEGORIES):
    """Create a user with categories (as create_user) and a password, all or nothing.

    `password_hash` and `salt` come from core.auth.hash_password; the password
    itself never reaches the database. Returns the new user id.
    """
    with transaction() as conn:
        user_id = _insert_user(conn, name, default_categories)
        _write_password(conn, user_id, password_hash, salt)
    return user_id


def _insert_user(conn, name, default_categories):
    """Insert a user and their starting categories on an open connection."""
    seeds = list(dict.fromkeys([*default_categories, FALLBACK_CATEGORY]))  # keep order, no duplicates
    name = name.strip()
    if not name:
        raise UserNameEmpty("User name cannot be empty.")
    if len(name) > MAX_NAME_LENGTH:
        raise UserNameTooLong(f"User name can be at most {MAX_NAME_LENGTH} characters.", max=MAX_NAME_LENGTH)
    # Names must be unique regardless of letter case ("Anna" / "anna" / "ANNA"),
    # so nobody can register a look-alike of an existing user. Done in Python:
    # SQLite's COLLATE NOCASE only folds A-Z, not Å/Ä/Ö.
    taken = {row[0].casefold() for row in conn.execute("SELECT name FROM users")}
    if name.casefold() in taken:
        raise UserNameTaken(f"A user named '{name}' already exists.", name=name)
    try:
        cursor = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
    except sqlite3.IntegrityError:
        raise UserNameTaken(f"A user named '{name}' already exists.", name=name) from None
    user_id = cursor.lastrowid
    conn.executemany(
        "INSERT INTO categories (name, user_id) VALUES (?, ?)",
        [(category, user_id) for category in seeds],
    )
    return user_id


def get_users():
    """Return all users as a list of User, sorted by name."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT id, name FROM users ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [User(*row) for row in rows]


def get_user(user_id):
    """Return the User with this id, or None if it does not exist."""
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT id, name FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return User(*row) if row else None


def get_user_by_name(name):
    """Return the User with this exact name (surrounding spaces ignored), or None."""
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT id, name FROM users WHERE name = ?", (name.strip(),)
        ).fetchone()
    return User(*row) if row else None


# --- Credentials ---------------------------------------------------------
# Only a salted hash is stored (see core/auth.py); never the password.


class Login(NamedTuple):
    """What is needed to check a login: the user and their stored hash and salt."""

    user: User
    password_hash: bytes
    salt: bytes


def get_login(name):
    """Return the Login for a user name, or None if the user does not exist or has no password."""
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT users.id, users.name, credentials.password_hash, credentials.salt
            FROM users JOIN credentials ON credentials.user_id = users.id
            WHERE users.name = ?
            """,
            (name.strip(),),
        ).fetchone()
    return Login(User(row[0], row[1]), row[2], row[3]) if row else None


def set_password(user_id, password_hash, salt):
    """Set or replace a user's password hash. Returns False if the user does not exist."""
    with transaction() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            return False
        _write_password(conn, user_id, password_hash, salt)
    return True


def get_max_price(user_id):
    """The user's highest price per item: their own choice, or MAX_PRICE if they made none."""
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT max_price FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else float(MAX_PRICE)


def set_max_price(user_id, max_price):
    """Set the user's highest price per item. Returns False if the user does not exist.

    Raises ValueError (and changes nothing) for a value outside
    MAX_PRICE_SETTING_MIN..MAX_PRICE_CEILING: the last guard, the UI checks
    this first with core.settings.max_price_problem.
    """
    if not MAX_PRICE_SETTING_MIN <= max_price <= MAX_PRICE_CEILING:
        raise ValueError("max price outside the allowed range")
    with transaction() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            return False
        conn.execute(
            """
            INSERT INTO settings (user_id, max_price) VALUES (?, ?)
            ON CONFLICT (user_id) DO UPDATE SET max_price = excluded.max_price
            """,
            (user_id, float(max_price)),
        )
    return True


def delete_user(user_id):
    """Delete a user and everything they own. Returns False if the user does not exist.

    Categories, memory, history, credentials and settings go with the user through
    ON DELETE CASCADE, in the same transaction. secure_delete makes SQLite
    overwrite the freed pages with zeros, so the data cannot be read back from
    the database file afterwards.
    """
    with transaction() as conn:
        conn.execute("PRAGMA secure_delete = ON")
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cursor.rowcount == 1


def _write_password(conn, user_id, password_hash, salt):
    conn.execute(
        """
        INSERT INTO credentials (user_id, password_hash, salt) VALUES (?, ?, ?)
        ON CONFLICT (user_id) DO UPDATE SET password_hash = excluded.password_hash, salt = excluded.salt
        """,
        (user_id, password_hash, salt),
    )


# --- Categories ----------------------------------------------------------


def get_categories(user_id):
    """Return the user's category names, sorted alphabetically."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT name FROM categories WHERE user_id = ? ORDER BY name COLLATE NOCASE",
            (user_id,),
        ).fetchall()
    return [row[0] for row in rows]


def add_category(user_id, name):
    """Add a category. Returns False if it is empty, too long, reserved or already exists.

    Reserved names are the fallback category's labels in every language
    ("Övrigt", "Other"), in any letter case, so a user's own category can
    never be mistaken for the fallback.
    """
    name = name.strip()
    if not _is_allowed_category_name(name):
        return False
    with transaction() as conn:
        return _insert_category(conn, user_id, name)


def _is_allowed_category_name(name):
    """Not empty, not too long and not one of the fallback category's reserved labels."""
    return bool(name) and len(name) <= MAX_NAME_LENGTH and name.casefold() not in _RESERVED_CATEGORY_NAMES


def _insert_category(conn, user_id, name):
    """Add a category on an open connection; False if the user already has it."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO categories (name, user_id) VALUES (?, ?)",
        (name, user_id),
    )
    return cursor.rowcount == 1


def delete_category(user_id, name):
    """Delete one of the user's categories. Returns True if it was removed.

    FALLBACK_CATEGORY can never be removed. The user's remembered items that
    pointed at the category are forgotten in the same transaction, so they
    fall back to FALLBACK_CATEGORY next time. History is left as it was saved.
    """
    if name == FALLBACK_CATEGORY:
        return False
    with transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM categories WHERE user_id = ? AND name = ?",
            (user_id, name),
        )
        if cursor.rowcount != 1:
            return False
        conn.execute(
            "DELETE FROM memory WHERE user_id = ? AND category = ?",
            (user_id, name),
        )
    return True


# --- Memory --------------------------------------------------------------


def load_memory(user_id):
    """Return the user's remembered item -> category mapping."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT item, category FROM memory WHERE user_id = ?", (user_id,)
        ).fetchall()
    return dict(rows)


def _category_names(conn, user_id):
    rows = conn.execute("SELECT name FROM categories WHERE user_id = ?", (user_id,)).fetchall()
    return {row[0] for row in rows}


def save_memory(user_id, mapping):
    """Remember item -> category choices, overwriting earlier ones.

    Choices are skipped if the item is empty or too long, or if the category
    is not one of the user's categories.
    """
    with transaction() as conn:
        _write_memory(conn, user_id, mapping)


def _write_memory(conn, user_id, mapping):
    """Write memory rows on an open connection (see save_memory); returns how many were written."""
    categories = _category_names(conn, user_id)
    rows = [
        (item, category, user_id)
        for item, category in mapping.items()
        if item and len(item) <= MAX_ITEM_LENGTH and category in categories
    ]
    if rows:
        conn.executemany(
            """
            INSERT INTO memory (item, category, user_id) VALUES (?, ?, ?)
            ON CONFLICT (user_id, item) DO UPDATE SET category = excluded.category
            """,
            rows,
        )
    return len(rows)


# --- History -------------------------------------------------------------


def save_history(user_id, purchase_date, items_df):
    """Save rows from a DataFrame with columns Item, Price, Category.

    Rows without an item or a price are skipped. A category that is not one of
    the user's categories is saved as FALLBACK_CATEGORY. Raises ValueError,
    and saves nothing, if an item is too long or a price is out of range.
    Returns the number of rows saved.
    """
    with transaction() as conn:
        return _write_history(conn, user_id, purchase_date, items_df)


def _checked_history_rows(items_df):
    """Return (item, price, category) for the rows to save, after the last-guard checks.

    Rows without an item or a price are dropped. Raises ValueError if an item
    is too long or a price is out of range.
    """
    rows = [
        (str(row.Item).strip(), float(row.Price), row.Category)
        for row in items_df.itertuples(index=False)
        if pd.notna(row.Item) and str(row.Item).strip() and pd.notna(row.Price)
    ]
    for item, price, _ in rows:
        if len(item) > MAX_ITEM_LENGTH:
            raise ValueError(f"Item names can be at most {MAX_ITEM_LENGTH} characters.")
        if not -MAX_PRICE <= price <= MAX_PRICE:
            raise ValueError(f"Prices must be between -{MAX_PRICE} and {MAX_PRICE} kr.")
    return rows


def _write_history(conn, user_id, purchase_date, items_df):
    """Write history rows on an open connection (see save_history)."""
    iso_date = _to_iso(purchase_date)
    candidates = _checked_history_rows(items_df)
    if not candidates:
        return 0

    categories = _category_names(conn, user_id)
    rows = [
        (iso_date, item, price, category if category in categories else FALLBACK_CATEGORY, user_id)
        for item, price, category in candidates
    ]
    conn.executemany(
        "INSERT INTO history (date, item, price, category, user_id) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


# --- Saving a receipt ----------------------------------------------------


def save_receipt(user_id, purchase_date, items_df, memory):
    """Save a receipt to history and learn its categories, all or nothing.

    `items_df` is written as in save_history and `memory` (item -> category)
    as in save_memory, in one transaction: if anything fails, neither history
    nor memory is changed, so saving again cannot create duplicates.
    Returns the number of history rows saved.
    """
    with transaction() as conn:
        saved = _write_history(conn, user_id, purchase_date, items_df)
        _write_memory(conn, user_id, memory)
    return saved


def get_history(user_id, start_date, end_date):
    """Return the user's purchases between two dates (inclusive) as a DataFrame."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT id, date, item, price, category FROM history
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date, id
            """,
            (user_id, _to_iso(start_date), _to_iso(end_date)),
        ).fetchall()
    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


def get_all_history(user_id):
    """Return all of the user's purchases, oldest first, as a DataFrame (for a backup)."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT id, date, item, price, category FROM history WHERE user_id = ? ORDER BY date, id",
            (user_id,),
        ).fetchall()
    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


class ImportCounts(NamedTuple):
    """How much import_user_data added."""

    categories: int
    memory: int
    purchases: int


def import_user_data(user_id, categories, memory, history_df):
    """Add categories, remembered choices and purchases from a backup, all or nothing.

    The usual rules apply: category names that are empty, too long or
    reserved are skipped (FALLBACK_CATEGORY is always there already);
    memory as in save_memory, written after the new categories so it can
    use them; purchases (columns Date, Item, Price, Category) as in
    save_history, so a category the user does not have becomes
    FALLBACK_CATEGORY and an item or price outside the limits raises
    ValueError. If anything fails, nothing is added.
    """
    with transaction() as conn:
        added_categories = sum(
            _insert_category(conn, user_id, name.strip())
            for name in categories
            if _is_allowed_category_name(name.strip())
        )
        added_memory = _write_memory(conn, user_id, memory)
        added_purchases = sum(
            _write_history(conn, user_id, purchase_date, rows[["Item", "Price", "Category"]])
            for purchase_date, rows in history_df.groupby("Date", sort=True)
        )
    return ImportCounts(added_categories, added_memory, added_purchases)


def get_history_dates(user_id):
    """Return the distinct dates the user has saved purchases on, newest first."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM history WHERE user_id = ? ORDER BY date DESC",
            (user_id,),
        ).fetchall()
    return [row[0] for row in rows]


class HistoryUpdate(NamedTuple):
    """What update_history_categories did: purchases changed, and ids that were not found."""

    changed: int
    missing: int


def update_history_categories(user_id, categories_by_id):
    """Give saved purchases a new category and remember it for their items, all or nothing.

    `categories_by_id` maps history ids to stored category names. Only the
    user's own purchases are changed (ids of other users' rows, or unknown
    ids, are skipped). A category the user does not have becomes
    FALLBACK_CATEGORY, as in save_history. Each changed item's category is
    remembered as in save_memory (FALLBACK_CATEGORY too: it was chosen);
    if one item gets several categories, the purchase with the highest id
    wins. Returns HistoryUpdate(changed, missing): how many purchases got
    another category, and how many ids were not found (deleted since the
    list was shown, e.g. in another tab, or not the user's).
    """
    with transaction() as conn:
        categories = _category_names(conn, user_id)
        changed = missing = 0
        memory = {}
        for history_id, category in sorted(categories_by_id.items()):
            stored = category if category in categories else FALLBACK_CATEGORY
            row = conn.execute(
                "SELECT item, category FROM history WHERE id = ? AND user_id = ?",
                (int(history_id), user_id),
            ).fetchone()
            if row is None:
                missing += 1  # not this user's purchase, or no such purchase (any more)
                continue
            item, old_category = row
            if stored != old_category:
                conn.execute(
                    "UPDATE history SET category = ? WHERE id = ? AND user_id = ?",
                    (stored, int(history_id), user_id),
                )
                changed += 1
            memory[item] = stored
        _write_memory(conn, user_id, memory)
    return HistoryUpdate(changed, missing)


def delete_history_date(user_id, purchase_date):
    """Delete all of the user's purchases on a date. Returns rows removed."""
    with transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM history WHERE user_id = ? AND date = ?",
            (user_id, _to_iso(purchase_date)),
        )
    return cursor.rowcount
