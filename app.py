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
from core.i18n import (
    DEFAULT_CATEGORIES,
    LANGUAGES,
    category_label,
    category_value,
    format_amount,
    resolve_language,
    t,
)
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

    `what` is the translation key naming the data, e.g. "what_history"; it is
    also used in the log and the button key. On a database error the message
    and button are shown and DataUnavailable is raised, so the rest of the
    section is skipped. Clicking the button reruns the page, which tries again.
    """
    try:
        return fetch(*args)
    except sqlite3.Error:
        logger.exception("Database error while loading %s", t(what, "en"))  # logs stay in English
        st.error(t("load_failed", lang(), what=t(what, lang())))
        st.button(t("try_again", lang()), key=f"retry_{what}")
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
    (flash, reset, st.rerun). `action` is the translation key completing
    "Could not ...", e.g. "action_save_receipt". Writes run in one
    transaction, so nothing is half-saved and the user's input stays on the
    page for another try.
    """
    try:
        yield
    except sqlite3.Error:
        logger.exception("Database error while trying to %s", t(action, "en"))  # logs stay in English
        st.error(t("write_failed", lang(), action=t(action, lang())))


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
    if "language" not in st.session_state:
        # First run in this browser tab: take the language from ?lang= (if valid).
        st.session_state.language = resolve_language(st.query_params.get("lang"))


# --- Language --------------------------------------------------------------
# The language lives in st.session_state.language and in the URL (?lang=sv),
# so it survives a page reload and can be bookmarked. It is not stored per user.


def lang():
    """The language currently selected in this browser tab."""
    return st.session_state.language


def sync_language_to_url():
    """Keep ?lang= in the address bar equal to the selected language."""
    if st.query_params.get("lang") != lang():
        st.query_params["lang"] = lang()


def render_language_selector():
    """Language picker at the top of the sidebar.

    Bound to st.session_state.language via its key, so changing it only
    changes the language; the draft receipt and everything else are kept.
    """
    st.sidebar.selectbox(
        "🌐 " + t("language_label", lang()),
        options=list(LANGUAGES),
        format_func=LANGUAGES.get,
        key="language",
        on_change=sync_language_to_url,
    )


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
        st.header(t("sidebar_user_header", lang()))

        users = load(db.get_users, what="what_users")
        user_names = {user.id: user.name for user in users}
        user_ids = list(user_names)
        current = st.session_state.current_user

        selected = st.selectbox(
            t("select_user", lang()),
            options=user_ids,
            format_func=user_names.get,
            index=user_ids.index(current) if current in user_ids else None,
            placeholder=t("choose_user_placeholder" if users else "no_users_placeholder", lang()),
        )
        if selected != current:
            switch_user(selected)
            st.rerun()

        with st.form("create_user_form", clear_on_submit=True):
            new_name = st.text_input(t("create_user_label", lang()), max_chars=MAX_NAME_LENGTH)
            submitted = st.form_submit_button(t("create_user_button", lang()))
        if submitted:
            with write_errors("action_create_user"):
                try:
                    new_id = db.create_user(new_name, DEFAULT_CATEGORIES[lang()])
                except db.UserNameError as error:
                    params = {name: escape_markdown(value) for name, value in error.params.items()}
                    st.error(t(error.key, lang(), **params))
                else:
                    switch_user(new_id)
                    st.rerun()


def render_category_manager(user_id, categories):
    """Expander with forms to add and remove the user's categories."""
    with st.expander(t("manage_categories", lang())):
        col_add, col_delete = st.columns(2)

        with col_add:
            with st.form("add_category_form", clear_on_submit=True):
                new_category = st.text_input(t("new_category", lang()), max_chars=MAX_NAME_LENGTH)
                add_clicked = st.form_submit_button(t("add_button", lang()))
            if add_clicked:
                with write_errors("action_add_category"):
                    if db.add_category(user_id, new_category):
                        flash("success", t("category_added", lang(), name=escape_markdown(new_category)))
                        st.rerun()
                    st.error(t("category_name_invalid", lang(), max=MAX_NAME_LENGTH))

        with col_delete:
            removable = [c for c in categories if c != FALLBACK_CATEGORY]
            with st.form("delete_category_form"):
                to_delete = st.selectbox(t("category_to_remove", lang()), options=removable)
                delete_clicked = st.form_submit_button(t("remove_button", lang()))
            if delete_clicked and to_delete:
                with write_errors("action_remove_category"):
                    if db.delete_category(user_id, to_delete):
                        flash("success", t("category_removed", lang(), name=escape_markdown(to_delete)))
                        st.rerun()
                    st.error(t("category_not_removed", lang(), name=escape_markdown(to_delete)))


def render_manual_entry(categories):
    """Form for adding a purchase by hand."""
    with st.expander(t("manual_entry", lang())):
        with st.form("manual_entry_form", clear_on_submit=True):
            col_item, col_price, col_category = st.columns([2, 1, 1])
            item = col_item.text_input(t("col_item", lang()), max_chars=MAX_ITEM_LENGTH)
            price = col_price.number_input(
                t("col_price", lang()),
                min_value=float(-MAX_PRICE),
                max_value=float(MAX_PRICE),
                value=0.0,
                step=1.0,
                format="%.2f",
            )
            # Options are the labels as shown ("Övrigt"); category_value maps the choice back.
            labels = [category_label(name, lang()) for name in categories]
            fallback_label = category_label(FALLBACK_CATEGORY, lang())
            category_shown = col_category.selectbox(
                t("col_category", lang()),
                options=labels,
                index=labels.index(fallback_label) if fallback_label in labels else 0,
            )
            submitted = st.form_submit_button(t("add_to_list", lang()))
        if submitted:
            if not item.strip():
                st.error(t("item_missing", lang()))
            else:
                category = category_value(category_shown, lang())
                add_to_draft(pd.DataFrame([{"Item": item.strip(), "Price": price, "Category": category}]))
                st.rerun()


def render_pdf_upload(user_id, categories):
    """Upload an ICA receipt, parse it and pre-fill categories from memory."""
    uploaded = st.file_uploader(
        t("upload_label", lang()),
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
            what="what_memory",
        )
    except NotAPdfError:
        st.error(t("not_a_pdf", lang()))
        return
    except ReceiptReadError:
        # The pypdf error is logged for debugging but not shown to the user.
        # Any other exception is a bug in our code and is left to Streamlit,
        # which logs the full traceback and shows a generic error.
        logger.warning("Could not read an uploaded PDF", exc_info=True)
        st.error(t("pdf_unreadable", lang()))
        return

    # A new key empties the uploader, so the same file is not imported again on rerun.
    st.session_state.upload_version += 1
    if result.items.empty:
        flash("warning", t("no_items_found", lang()))
    else:
        add_to_draft(result.items)
        if result.purchase_date:
            set_purchase_date(result.purchase_date)
        flash("success", import_message(result))
    st.rerun()


def import_message(result):
    """Text shown after a receipt PDF has been imported."""
    added = t("import_added", lang(), count=len(result.items), remembered=result.remembered)
    if result.purchase_date:
        return f"{added} {t('import_date_set', lang(), date=f'{result.purchase_date:%Y-%m-%d}')}"
    return f"{added} {t('import_no_date', lang())}"


def render_receipt_editor(categories):
    """Editable table of the current receipt."""
    # The editor shows category labels ("Övrigt"); on_editor_change maps them back.
    shown = draft_ops.with_category_labels(st.session_state.receipt_df, lang())
    labels = {category_label(name, lang()) for name in categories}
    # Keep categories that were deleted after being assigned, so they still display.
    options = sorted(labels | set(shown["Category"].dropna()), key=str.lower)

    st.data_editor(
        shown,
        key=editor_key(),
        on_change=on_editor_change,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Item": st.column_config.TextColumn(t("col_item", lang()), required=True, max_chars=MAX_ITEM_LENGTH),
            "Price": st.column_config.NumberColumn(
                t("col_price", lang()),
                format="%.2f",
                required=True,
                min_value=-MAX_PRICE,
                max_value=MAX_PRICE,
            ),
            "Category": st.column_config.SelectboxColumn(
                t("col_category", lang()), options=options, required=True
            ),
        },
    )


def render_save_section(user_id):
    """Pick a date and save the receipt to history; learn categories into memory."""
    draft = st.session_state.receipt_df

    col_date, col_save, col_clear = st.columns([2, 1, 1], vertical_alignment="bottom")
    purchase_date = col_date.date_input(
        t("purchase_date", lang()),
        value=st.session_state.purchase_date,
        key=date_key(),
        on_change=remember_picked_date,
        format="YYYY-MM-DD",
    )

    if col_save.button(t("save_button", lang()), type="primary", width="stretch"):
        with write_errors("action_save_receipt"):
            try:
                saved = receipts.save_receipt(user_id, purchase_date, draft)
            except receipts.InvalidReceipt as error:
                problems = "\n".join(f"- {t(p.key, lang(), **p.params)}" for p in error.problems)
                st.error(f"{t('not_saved', lang())}\n\n{problems}")
                return
            set_draft(draft_ops.empty_receipt())
            set_purchase_date(date.today())
            flash("success", t("saved_rows", lang(), count=saved, date=f"{purchase_date:%Y-%m-%d}"))
            st.rerun()

    if col_clear.button(t("clear_list", lang()), width="stretch"):
        set_draft(draft_ops.empty_receipt())
        set_purchase_date(date.today())
        st.rerun()


def render_current_receipt_tab():
    """Tab 1: build the current receipt and save it to history."""
    user_id = st.session_state.current_user
    categories = load(db.get_categories, user_id, what="what_categories")

    render_category_manager(user_id, categories)
    render_manual_entry(categories)
    render_pdf_upload(user_id, categories)

    if st.session_state.receipt_df.empty:
        st.info(t("empty_draft_info", lang()))
        return

    st.subheader(t("current_list", lang()))
    render_receipt_editor(categories)
    st.metric(t("total", lang()), format_amount(total_cost(st.session_state.receipt_df), lang()))
    render_save_section(user_id)


def render_delete_date(user_id):
    """Expander for removing everything saved on one date."""
    saved_dates = load(db.get_history_dates, user_id, what="what_saved_dates")
    if not saved_dates:
        return

    with st.expander(t("delete_receipt_expander", lang())):
        with st.form("delete_date_form"):
            to_delete = st.selectbox(t("col_date", lang()), options=saved_dates)
            confirmed = st.checkbox(t("confirm_delete", lang()))
            delete_clicked = st.form_submit_button(t("delete_button", lang()))
        if delete_clicked:
            if not confirmed:
                st.error(t("tick_to_confirm", lang()))
            else:
                with write_errors("action_delete_receipt"):
                    removed = db.delete_history_date(user_id, to_delete)
                    flash("success", t("deleted_rows", lang(), count=removed, date=to_delete))
                    st.rerun()


def render_history_tab():
    """Tab 2: total spent and spending per category for a period."""
    user_id = st.session_state.current_user
    today = date.today()

    col_start, col_end = st.columns(2)
    start_date = col_start.date_input(t("start_date", lang()), value=today.replace(day=1), format="YYYY-MM-DD")
    end_date = col_end.date_input(t("end_date", lang()), value=today, format="YYYY-MM-DD")

    if start_date > end_date:
        st.error(t("start_after_end", lang()))
        return

    history = load(db.get_history, user_id, start_date, end_date, what="what_history")
    if history.empty:
        st.info(t("no_purchases_period", lang()))
    else:
        col_total, col_count = st.columns(2)
        col_total.metric(t("total_spent", lang()), format_amount(total_cost(history), lang()))
        col_count.metric(t("purchases", lang()), len(history))

        by_category = sum_by_category(history).rename(index=lambda name: category_label(name, lang()))
        st.subheader(t("spending_per_category", lang()))
        st.bar_chart(
            # y is the value column ("kr"), also when the bars are horizontal.
            by_category, y="Price", x_label=t("col_category", lang()), y_label="kr",
            horizontal=True, sort="-Price",
        )

        with st.expander(t("show_all_purchases", lang())):
            st.dataframe(
                draft_ops.with_category_labels(history.drop(columns="Id"), lang()),
                hide_index=True,
                width="stretch",
                column_config={
                    "Date": st.column_config.TextColumn(t("col_date", lang())),
                    "Item": st.column_config.TextColumn(t("col_item", lang())),
                    "Price": st.column_config.NumberColumn(t("col_price", lang()), format="%.2f"),
                    "Category": st.column_config.TextColumn(t("col_category", lang())),
                },
            )

    render_delete_date(user_id)


def main():
    st.set_page_config(page_title="ExpenseHandler", page_icon="🧾", layout="centered")
    init_session_state()
    sync_language_to_url()
    render_language_selector()
    st.title(t("app_title", lang()))

    try:
        load(setup_database, what="what_database")
        render_user_sidebar()
        user_id = st.session_state.current_user
        user = load(db.get_user, user_id, what="what_selected_user") if user_id else None
    except DataUnavailable:
        return  # Without users nothing else can be shown; "Try again" reruns.

    if user is None:
        st.info(t("select_or_create_user", lang()))
        return

    st.caption(t("showing_data_for", lang(), name=escape_markdown(user.name)))
    show_flash()

    tab_receipt, tab_history = st.tabs([t("tab_receipt", lang()), t("tab_history", lang())])
    with tab_receipt:
        render_section(render_current_receipt_tab)
    with tab_history:
        render_section(render_history_tab)


main()
