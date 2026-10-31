"""ExpenseHandler - Streamlit UI.

Run with: python -m streamlit run app.py
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import date

import pandas as pd
import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from core.calculator import sum_by_category, total_cost
from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_NAME_LENGTH, MAX_PRICE
from core.parser import NotAPdfError, ReceiptReadError
from core.text import escape_markdown
from integrations import db
from services import receipts

logger = logging.getLogger(__name__)


# --- Database error handling ---------------------------------------------
# Database errors (e.g. "database is locked") are caught here, at the UI
# boundary, logged without any receipt data and shown as a short message.


class DataUnavailable(Exception):
    """Raised by load() after it has shown an error; stops one page section."""


def load(fetch, *args, what):
    """Read from the database, or show an error with a "Try again" button.

    `what` names the data for the message and the button key, e.g. "your
    history". On a database error the message and button are shown and
    DataUnavailable is raised, so the rest of the section is skipped.
    Clicking the button reruns the page, which tries again.
    """
    try:
        return fetch(*args)
    except sqlite3.Error:
        logger.exception("Database error while loading %s", what)
        st.error(f"Could not load {what}. The database may be busy.")
        st.button("🔄 Try again", key=f"retry_{what}")
        raise DataUnavailable from None


def render_section(render, *args):
    """Run a render function; a failed load() only stops that section."""
    try:
        render(*args)
    except DataUnavailable:
        pass


@contextmanager
def write_errors(action):
    """Show a message instead of crashing when a database write fails.

    Wrap the write and everything that should only happen after it succeeds
    (flash, reset, st.rerun). `action` completes "Could not ...". Writes run
    in one transaction, so nothing is half-saved and the user's input stays
    on the page for another try.
    """
    try:
        yield
    except sqlite3.Error:
        logger.exception("Database error while trying to %s", action)
        st.error(f"Could not {action}. The database may be busy; please try again.")


@st.cache_resource
def setup_database():
    """Create the database tables once per server process."""
    db.init_db()
    return True


def init_session_state():
    """Set default values for everything the app keeps between reruns."""
    defaults = {
        "current_user": None,
        "receipt_df": draft_ops.empty_receipt(),
        "table_version": 0,
        "upload_version": 0,
        "purchase_date": date.today(),
        "date_version": 0,
        "flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def switch_user(user_id):
    """Select a user and drop the previous user's unsaved receipt."""
    st.session_state.current_user = user_id
    set_draft(draft_ops.empty_receipt())
    set_purchase_date(date.today())


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


def add_to_draft(rows):
    set_draft(draft_ops.add_rows(st.session_state.receipt_df, rows))


def editor_key():
    return f"receipt_editor_{st.session_state.table_version}"


def on_editor_change():
    """on_change for st.data_editor: fold its edits into receipt_df.

    The editor reports changes relative to the data it was given, so they are
    applied to receipt_df and the key is bumped. This keeps one source of truth
    and avoids edits being applied twice on the next rerun.
    """
    changes = st.session_state[editor_key()]
    set_draft(draft_ops.apply_editor_changes(st.session_state.receipt_df, changes))


def flash(kind, message):
    """Show a message after the next rerun (st.rerun would hide it otherwise)."""
    st.session_state.flash = (kind, message)


def show_flash():
    """Show the pending flash message, if any.

    It is drawn inside a container that is rendered on every run, even when
    empty. Otherwise the tabs below would move up when the message goes away,
    Streamlit would treat them as new tabs and jump back to the first one.
    """
    with st.container():
        if st.session_state.flash:
            kind, message = st.session_state.flash
            getattr(st, kind)(message)
            st.session_state.flash = None


def render_user_sidebar():
    """Sidebar for selecting an existing user or creating a new one."""
    with st.sidebar:
        st.header("👤 User")

        users = load(db.get_users, what="the list of users")
        user_names = {user.id: user.name for user in users}
        user_ids = list(user_names)
        current = st.session_state.current_user

        selected = st.selectbox(
            "Select user",
            options=user_ids,
            format_func=user_names.get,
            index=user_ids.index(current) if current in user_ids else None,
            placeholder="Choose a user..." if users else "No users yet",
        )
        if selected != current:
            switch_user(selected)
            st.rerun()

        with st.form("create_user_form", clear_on_submit=True):
            new_name = st.text_input("Create new user", max_chars=MAX_NAME_LENGTH)
            submitted = st.form_submit_button("➕ Create user")
        if submitted:
            with write_errors("create the user"):
                try:
                    new_id = db.create_user(new_name)
                except ValueError as error:
                    st.error(escape_markdown(error))
                else:
                    switch_user(new_id)
                    st.rerun()


def render_category_manager(user_id, categories):
    """Expander with forms to add and remove the user's categories."""
    with st.expander("⚙️ Manage categories"):
        col_add, col_delete = st.columns(2)

        with col_add:
            with st.form("add_category_form", clear_on_submit=True):
                new_category = st.text_input("New category", max_chars=MAX_NAME_LENGTH)
                add_clicked = st.form_submit_button("➕ Add")
            if add_clicked:
                with write_errors("add the category"):
                    if db.add_category(user_id, new_category):
                        flash("success", f"Added category '{escape_markdown(new_category)}'.")
                        st.rerun()
                    st.error(f"Enter a name of 1–{MAX_NAME_LENGTH} characters that is not already in the list.")

        with col_delete:
            removable = [c for c in categories if c != FALLBACK_CATEGORY]
            with st.form("delete_category_form"):
                to_delete = st.selectbox("Category to remove", options=removable)
                delete_clicked = st.form_submit_button("🗑️ Remove")
            if delete_clicked and to_delete:
                with write_errors("remove the category"):
                    if db.delete_category(user_id, to_delete):
                        flash("success", f"Removed category '{escape_markdown(to_delete)}'.")
                        st.rerun()
                    st.error(f"Category '{escape_markdown(to_delete)}' could not be removed.")


def render_manual_entry(categories):
    """Form for adding a purchase by hand."""
    with st.expander("✍️ Add a purchase manually"):
        with st.form("manual_entry_form", clear_on_submit=True):
            col_item, col_price, col_category = st.columns([2, 1, 1])
            item = col_item.text_input("Item", max_chars=MAX_ITEM_LENGTH)
            price = col_price.number_input(
                "Price (kr)",
                min_value=float(-MAX_PRICE),
                max_value=float(MAX_PRICE),
                value=0.0,
                step=1.0,
                format="%.2f",
            )
            category = col_category.selectbox(
                "Category",
                options=categories,
                index=categories.index(FALLBACK_CATEGORY) if FALLBACK_CATEGORY in categories else 0,
            )
            submitted = st.form_submit_button("➕ Add to list")
        if submitted:
            if not item.strip():
                st.error("Enter an item description.")
            else:
                add_to_draft(pd.DataFrame([{"Item": item.strip(), "Price": price, "Category": category}]))
                st.rerun()


def render_pdf_upload(user_id, categories):
    """Upload an ICA receipt, parse it and pre-fill categories from memory."""
    uploaded = st.file_uploader(
        "Upload an ICA receipt (.pdf)",
        type="pdf",
        key=f"pdf_upload_{st.session_state.upload_version}",
    )
    if uploaded is None:
        return

    try:
        # A database error here goes through load(): the file stays in the
        # uploader and "Try again" imports it again.
        result = load(
            receipts.import_receipt, user_id, uploaded.getvalue(), categories,
            what="your remembered categories",
        )
    except NotAPdfError:
        st.error("The file is not a PDF. Upload the receipt as a PDF from ICA.")
        return
    except ReceiptReadError:
        # The pypdf error is logged for debugging but not shown to the user.
        # Any other exception is a bug in our code and is left to Streamlit,
        # which logs the full traceback and shows a generic error.
        logger.warning("Could not read an uploaded PDF", exc_info=True)
        st.error("Could not read the PDF. Check that it is an ICA receipt and try again.")
        return

    # A new key empties the uploader, so the same file is not imported again on rerun.
    st.session_state.upload_version += 1
    if result.items.empty:
        flash("warning", "No items were found in the PDF.")
    else:
        add_to_draft(result.items)
        if result.purchase_date:
            set_purchase_date(result.purchase_date)
        flash("success", import_message(result))
    st.rerun()


def import_message(result):
    """Text shown after a receipt PDF has been imported."""
    message = f"Added {len(result.items)} items ({result.remembered} categorized from memory)."
    if result.purchase_date:
        return message + f" Purchase date set to {result.purchase_date:%Y-%m-%d} from the receipt."
    return message + " No date found on the receipt; check the purchase date."


def render_receipt_editor(categories):
    """Editable table of the current receipt."""
    draft = st.session_state.receipt_df
    # Keep categories that were deleted after being assigned, so they still display.
    options = sorted(set(categories) | set(draft["Category"].dropna()), key=str.lower)

    st.data_editor(
        draft,
        key=editor_key(),
        on_change=on_editor_change,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Item": st.column_config.TextColumn("Item", required=True, max_chars=MAX_ITEM_LENGTH),
            "Price": st.column_config.NumberColumn(
                "Price (kr)",
                format="%.2f",
                required=True,
                min_value=-MAX_PRICE,
                max_value=MAX_PRICE,
            ),
            "Category": st.column_config.SelectboxColumn("Category", options=options, required=True),
        },
    )


def render_save_section(user_id):
    """Pick a date and save the receipt to history; learn categories into memory."""
    draft = st.session_state.receipt_df

    col_date, col_save, col_clear = st.columns([2, 1, 1], vertical_alignment="bottom")
    purchase_date = col_date.date_input(
        "Purchase date",
        value=st.session_state.purchase_date,
        key=date_key(),
        on_change=remember_picked_date,
        format="YYYY-MM-DD",
    )

    if col_save.button("💾 Save", type="primary", width="stretch"):
        with write_errors("save the receipt"):
            try:
                saved = receipts.save_receipt(user_id, purchase_date, draft)
            except receipts.InvalidReceipt as error:
                st.error("The receipt was not saved:\n\n" + "\n".join(f"- {p}" for p in error.problems))
                return
            set_draft(draft_ops.empty_receipt())
            set_purchase_date(date.today())
            flash("success", f"Saved {saved} rows for {purchase_date:%Y-%m-%d}.")
            st.rerun()

    if col_clear.button("🗑️ Clear list", width="stretch"):
        set_draft(draft_ops.empty_receipt())
        set_purchase_date(date.today())
        st.rerun()


def render_current_receipt_tab():
    """Tab 1: build the current receipt and save it to history."""
    user_id = st.session_state.current_user
    categories = load(db.get_categories, user_id, what="your categories")

    render_category_manager(user_id, categories)
    render_manual_entry(categories)
    render_pdf_upload(user_id, categories)

    if st.session_state.receipt_df.empty:
        st.info("Add a purchase manually or upload a receipt to get started.")
        return

    st.subheader("Current list")
    render_receipt_editor(categories)
    st.metric("Total", f"{total_cost(st.session_state.receipt_df):.2f} kr")
    render_save_section(user_id)


def render_delete_date(user_id):
    """Expander for removing everything saved on one date."""
    saved_dates = load(db.get_history_dates, user_id, what="your saved dates")
    if not saved_dates:
        return

    with st.expander("🗑️ Delete a saved receipt"):
        with st.form("delete_date_form"):
            to_delete = st.selectbox("Date", options=saved_dates)
            confirmed = st.checkbox("Yes, delete every purchase saved on this date")
            delete_clicked = st.form_submit_button("Delete")
        if delete_clicked:
            if not confirmed:
                st.error("Tick the box to confirm.")
            else:
                with write_errors("delete the receipt"):
                    removed = db.delete_history_date(user_id, to_delete)
                    flash("success", f"Deleted {removed} rows from {to_delete}.")
                    st.rerun()


def render_history_tab():
    """Tab 2: total spent and spending per category for a period."""
    user_id = st.session_state.current_user
    today = date.today()

    col_start, col_end = st.columns(2)
    start_date = col_start.date_input("Start date", value=today.replace(day=1), format="YYYY-MM-DD")
    end_date = col_end.date_input("End date", value=today, format="YYYY-MM-DD")

    if start_date > end_date:
        st.error("The start date must be on or before the end date.")
        return

    history = load(db.get_history, user_id, start_date, end_date, what="your history")
    if history.empty:
        st.info("No purchases saved in this period.")
    else:
        col_total, col_count = st.columns(2)
        col_total.metric("Total spent", f"{total_cost(history):.2f} kr")
        col_count.metric("Purchases", len(history))

        by_category = sum_by_category(history)
        st.subheader("Spending per category")
        st.bar_chart(by_category, y="Price", y_label="kr", horizontal=True, sort="-Price")

        with st.expander("Show all purchases"):
            st.dataframe(
                history.drop(columns="Id"),
                hide_index=True,
                width="stretch",
                column_config={"Price": st.column_config.NumberColumn("Price (kr)", format="%.2f")},
            )

    render_delete_date(user_id)


def main():
    st.set_page_config(page_title="ExpenseHandler", page_icon="🧾", layout="centered")
    init_session_state()
    st.title("🧾 ExpenseHandler")

    try:
        load(setup_database, what="the database")
        render_user_sidebar()
        user_id = st.session_state.current_user
        user = load(db.get_user, user_id, what="the selected user") if user_id else None
    except DataUnavailable:
        return  # Without users nothing else can be shown; "Try again" reruns.

    if user is None:
        st.info("Select or create a user in the sidebar to get started.")
        return

    st.caption(f"Showing data for **{escape_markdown(user.name)}**")
    show_flash()

    tab_receipt, tab_history = st.tabs(["🛒 Current Receipt", "📜 History"])
    with tab_receipt:
        render_section(render_current_receipt_tab)
    with tab_history:
        render_section(render_history_tab)


main()
