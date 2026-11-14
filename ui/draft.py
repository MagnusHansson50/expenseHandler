"""The receipt being edited (the draft) in session state: replacing it, adding rows, folding in
st.data_editor edits, and the purchase date picker.
"""

import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from ui.common import lang


def set_purchase_date(value):
    """Set the date shown in the date picker; a new key makes the picker show it."""
    st.session_state.purchase_date = value
    st.session_state.date_version += 1


def date_key():
    return f"purchase_date_{st.session_state.date_version}"


def remember_picked_date():
    """on_change for the date picker: keep the user's own choice."""
    st.session_state.purchase_date = st.session_state[date_key()]


def set_draft(df):
    """Replace the draft receipt and give st.data_editor a fresh key so it redraws."""
    st.session_state.receipt_df = draft_ops.normalize_receipt(df)
    st.session_state.table_version += 1
    if st.session_state.receipt_df.empty:
        # A new receipt (cleared, saved, logged in or out) starts without an
        # ongoing review or a "Not now" answer.
        st.session_state.review_active = False
        st.session_state.review_dismissed = []
        st.session_state.review_kept_fallback = []
        st.session_state.review_notice = None
        st.session_state.review_category_message = None
        st.session_state.review_pending_category = None
        st.session_state.paid_total = None
        st.session_state.removed_total = 0.0
        st.session_state.imported_rows = []


def add_to_draft(rows):
    set_draft(draft_ops.add_rows(st.session_state.receipt_df, rows))


def editor_key():
    # The language is part of the key: the editor shows translated category
    # labels, so a language switch gives it new data and must start it fresh.
    return f"receipt_editor_{lang()}_{st.session_state.table_version}"


def on_editor_change():
    """on_change for st.data_editor: fold its edits into receipt_df.

    The editor reports changes relative to the data it was given, so they are
    applied to receipt_df and the key is bumped. This keeps one source of truth
    and avoids edits being applied twice on the next rerun. Category labels
    picked in the editor are turned back into stored names first.
    """
    changes = draft_ops.changes_to_stored_categories(st.session_state[editor_key()], lang())
    draft = st.session_state.receipt_df
    deleted = [int(row) for row in changes.get("deleted_rows", []) if 0 <= int(row) < len(draft)]
    note_removed(draft.iloc[deleted])
    set_draft(draft_ops.apply_editor_changes(draft, changes))


def note_removed(rows):
    """Count rows removed from an uploaded receipt as removed on purpose (see render_paid_comparison).

    Only rows that came from the upload (imported_rows, as item and price) count: something
    added by hand and removed again was never on the receipt. Called before set_draft,
    which forgets both with paid_total when the draft becomes empty.
    """
    if st.session_state.paid_total is None:
        return
    for item, price in zip(rows["Item"], rows["Price"], strict=True):
        key = [item, price]
        if key in st.session_state.imported_rows:
            st.session_state.imported_rows.remove(key)
            st.session_state.removed_total = round(st.session_state.removed_total + float(price), 2)
