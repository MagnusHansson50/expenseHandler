"""Export and import of one user's own data (core.backup + database, no Streamlit).

Errors for the UI to handle:
- core.backup.InvalidBackup(problems) when a file cannot be imported
- sqlite3.Error when the database fails
"""

from datetime import date

from core.backup import history_csv, make_backup, new_categories, new_history_rows, new_memory, read_backup
from integrations import db


def export_backup(user_id, today=None):
    """The user's backup file (bytes): categories, remembered choices and all purchases."""
    return make_backup(
        db.get_categories(user_id),
        db.load_memory(user_id),
        db.get_all_history(user_id),
        today or date.today(),
    )


def export_history_csv(user_id, lang):
    """All of the user's purchases as CSV for a spreadsheet in `lang`."""
    return history_csv(db.get_all_history(user_id), lang)


def import_backup(user_id, data):
    """Read a backup file and add what the user does not have yet, all or nothing.

    Raises InvalidBackup (nothing added) if the file has problems. Returns
    db.ImportCounts: how many categories, remembered choices and purchases
    were added. Importing the same file again adds nothing.
    """
    backup = read_backup(data)
    return db.import_user_data(
        user_id,
        new_categories(db.get_categories(user_id), backup.categories),
        new_memory(db.load_memory(user_id), backup.memory),
        new_history_rows(db.get_all_history(user_id), backup.history),
    )
