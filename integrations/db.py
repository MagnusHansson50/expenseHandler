"""SQLite data layer for ExpenseHandler.

Every table except `users` is tied to a user, and every function that touches
those tables takes a `user_id` so one user's data can never leak into another's.
"""

import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pandas as pd

# EXPENSES_DB_PATH lets tests and local experiments use a separate database file.
DB_PATH = Path(
    os.environ.get("EXPENSES_DB_PATH")
    or Path(__file__).resolve().parent.parent / "expenses.db"
)

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
    "Other",
]

HISTORY_COLUMNS = ["Id", "Date", "Item", "Price", "Category"]


def get_connection():
    """Open a new connection. Callers close it via `closing(...)`."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist yet."""
    with closing(get_connection()) as conn, conn:
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
            """
        )


def _to_iso(value):
    """Normalize a date or 'YYYY-MM-DD' string to an ISO date string."""
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


# --- Users ---------------------------------------------------------------


def create_user(name):
    """Create a user, seed default categories and return the new id.

    Raises ValueError if the name is empty or already taken.
    """
    name = name.strip()
    if not name:
        raise ValueError("User name cannot be empty.")

    with closing(get_connection()) as conn, conn:
        try:
            cursor = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            raise ValueError(f"A user named '{name}' already exists.") from None
        user_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO categories (name, user_id) VALUES (?, ?)",
            [(category, user_id) for category in DEFAULT_CATEGORIES],
        )
    return user_id


def get_users():
    """Return all users as a list of (id, name) tuples, sorted by name."""
    with closing(get_connection()) as conn:
        return conn.execute(
            "SELECT id, name FROM users ORDER BY name COLLATE NOCASE"
        ).fetchall()


def get_user(user_id):
    """Return (id, name) for a user, or None if it does not exist."""
    with closing(get_connection()) as conn:
        return conn.execute(
            "SELECT id, name FROM users WHERE id = ?", (user_id,)
        ).fetchone()


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
    """Add a category. Returns False if it is empty or already exists."""
    name = name.strip()
    if not name:
        return False
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO categories (name, user_id) VALUES (?, ?)",
            (name, user_id),
        )
    return cursor.rowcount == 1


def delete_category(user_id, name):
    """Delete a category. Returns True if a row was removed."""
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            "DELETE FROM categories WHERE user_id = ? AND name = ?",
            (user_id, name),
        )
    return cursor.rowcount == 1


# --- Memory --------------------------------------------------------------


def load_memory(user_id):
    """Return the user's remembered item -> category mapping."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT item, category FROM memory WHERE user_id = ?", (user_id,)
        ).fetchall()
    return dict(rows)


def save_memory(user_id, mapping):
    """Remember item -> category choices, overwriting earlier ones."""
    rows = [
        (item, category, user_id)
        for item, category in mapping.items()
        if item and category
    ]
    if not rows:
        return
    with closing(get_connection()) as conn, conn:
        conn.executemany(
            """
            INSERT INTO memory (item, category, user_id) VALUES (?, ?, ?)
            ON CONFLICT (user_id, item) DO UPDATE SET category = excluded.category
            """,
            rows,
        )


# --- History -------------------------------------------------------------


def save_history(user_id, purchase_date, items_df):
    """Save rows from a DataFrame with columns Item, Price, Category.

    Returns the number of rows saved.
    """
    iso_date = _to_iso(purchase_date)
    rows = [
        (iso_date, row.Item, float(row.Price), row.Category, user_id)
        for row in items_df.itertuples(index=False)
        if pd.notna(row.Item) and str(row.Item).strip() and pd.notna(row.Price)
    ]
    if not rows:
        return 0
    with closing(get_connection()) as conn, conn:
        conn.executemany(
            "INSERT INTO history (date, item, price, category, user_id) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


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


def get_history_dates(user_id):
    """Return the distinct dates the user has saved purchases on, newest first."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM history WHERE user_id = ? ORDER BY date DESC",
            (user_id,),
        ).fetchall()
    return [row[0] for row in rows]


def delete_history_date(user_id, purchase_date):
    """Delete all of the user's purchases on a date. Returns rows removed."""
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            "DELETE FROM history WHERE user_id = ? AND date = ?",
            (user_id, _to_iso(purchase_date)),
        )
    return cursor.rowcount
