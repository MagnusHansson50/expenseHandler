"""The "Backup" section of the History tab: download a backup or CSV, and read a backup back in.
"""

from datetime import date

import streamlit as st

from core.backup import InvalidBackup, download_name
from core.i18n import t
from core.text import escape_markdown
from integrations import db
from services import backup
from ui.common import flash, lang, load, write_errors

# --- Backup ----------------------------------------------------------------
# Only the logged-in user's own data is exported or imported. The import
# merges (core/backup.py): what the user already has is kept, and importing
# the same file again adds nothing.

MAX_PROBLEMS_SHOWN = 20


def render_backup(user_id):
    """Expander to download a backup or the history as CSV, and to read a backup back in."""
    with st.expander(t("backup_header", lang())):
        st.caption(t("backup_intro", lang()))
        user = load(db.get_user, user_id, what="what_selected_user")
        today = date.today()
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            t("backup_download_button", lang()),
            data=load(backup.export_backup, user_id, what="what_backup"),
            file_name=download_name(user.name, today, "json"),
            mime="application/json",
            key="backup_download",
        )
        col_csv.download_button(
            t("backup_csv_button", lang()),
            data=load(backup.export_history_csv, user_id, lang(), what="what_history"),
            file_name=download_name(user.name, today, "csv"),
            mime="text/csv",
            key="backup_csv_download",
        )

        uploaded = st.file_uploader(
            t("backup_upload_label", lang()),
            type="json",
            key=f"backup_upload_{st.session_state.backup_upload_version}",
        )
        if uploaded is not None:
            import_backup_file(user_id, uploaded.getvalue())


def import_backup_file(user_id, data):
    """Import an uploaded backup; show what was added, or why nothing was."""
    # A new key empties the uploader, so the same file is not imported again on the next run.
    st.session_state.backup_upload_version += 1
    with write_errors("action_import_backup"):
        try:
            added = backup.import_backup(user_id, data)
        except InvalidBackup as error:
            st.error(backup_problems_text(error.problems))
            return
        if any(added):
            flash("success", t(
                "backup_imported", lang(),
                purchases=added.purchases, categories=added.categories, memory=added.memory,
            ))
        else:
            flash("info", t("backup_nothing_new", lang()))
        st.rerun()


def backup_problems_text(problems):
    """The reasons a backup was not imported, as a Markdown list (names from the file escaped)."""
    lines = []
    for problem in problems[:MAX_PROBLEMS_SHOWN]:
        params = {
            key: escape_markdown(value) if isinstance(value, str) else value
            for key, value in problem.params.items()
        }
        lines.append(f"- {t(problem.key, lang(), **params)}")
    if len(problems) > MAX_PROBLEMS_SHOWN:
        lines.append(f"- {t('backup_more_problems', lang(), count=len(problems) - MAX_PROBLEMS_SHOWN)}")
    return t("backup_not_imported", lang()) + "\n\n" + "\n".join(lines)
