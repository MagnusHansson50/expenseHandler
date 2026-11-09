"""Flows for saved purchases that combine core logic with the database.

No Streamlit here; sqlite3.Error is passed on for the UI to handle.
"""

from core.history import category_changes
from integrations import db


def change_categories(user_id, history, editor_changes, lang):
    """Save the categories changed in the history list, and remember them for their items.

    `history` and `editor_changes` are as in core.history.category_changes.
    Returns the number of purchases whose category changed (0 if none did,
    without touching the database).
    """
    changes = category_changes(history, editor_changes, lang)
    if not changes:
        return 0
    return db.update_history_categories(user_id, changes)
