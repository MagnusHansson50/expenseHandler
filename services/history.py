"""Flows for saved purchases that combine core logic with the database.

No Streamlit here; sqlite3.Error is passed on for the UI to handle.
"""

from core.history import category_changes
from integrations import db


def change_categories(user_id, shown, editor_changes, lang):
    """Save the categories changed in the history list, and remember them for their items.

    `shown` is the list exactly as it was shown when the edits were made (the
    editor reports rows by position, so they must be mapped on that list, not
    on one loaded again since: another tab may have deleted purchases in
    between). `editor_changes` is as in core.history.category_changes.
    Returns db.HistoryUpdate(changed, missing); (0, 0) without touching the
    database when nothing was changed.
    """
    changes = category_changes(shown, editor_changes, lang)
    if not changes:
        return db.HistoryUpdate(0, 0)
    return db.update_history_categories(user_id, changes)
