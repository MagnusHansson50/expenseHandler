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
from core.calculator import paid_difference, sum_by_category, total_cost
from core.constants import (
    FALLBACK_CATEGORY,
    MAX_ITEM_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PASSWORD_LENGTH,
    MAX_PRICE,
)
from core.i18n import (
    DEFAULT_CATEGORIES,
    LANGUAGES,
    category_label,
    category_value,
    format_amount,
    format_number,
    resolve_language,
    t,
)
from core.backup import InvalidBackup, download_name
from core.parser import NotAPdfError, ReceiptReadError
from core.text import escape_markdown
from integrations import db
from services import auth, backup, receipts

logger = logging.getLogger(__name__)

# Number format for prices in st.number_input, st.data_editor and st.dataframe.
# These widgets only accept printf-style formats, which always use a decimal
# point, so tables show "1122.17" in every language. Totals and messages are
# formatted per language with format_amount / format_number instead.
PRICE_INPUT_FORMAT = "%.2f"


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
        "backup_upload_version": 0,
        "purchase_date": date.today(),
        "date_version": 0,
        "flash": None,
        "review_active": False,
        "review_dismissed": [],
        "review_handled": [],
        "review_skipped": [],
        "review_names": [],
        "review_notice": None,
        "review_category_message": None,
        "review_kept_fallback": [],
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
    if st.session_state.receipt_df.empty:
        # A new receipt (cleared, saved, logged in or out) starts without an
        # ongoing review or a "Not now" answer.
        st.session_state.review_active = False
        st.session_state.review_dismissed = []
        st.session_state.review_kept_fallback = []
        st.session_state.review_notice = None
        st.session_state.review_category_message = None


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


# --- Login ---------------------------------------------------------------
# st.session_state.current_user is only ever set by log_in(), after a
# successful login or registration. The forms are handled in on_click
# callbacks, which run before the page is drawn: they read the password once
# and empty the password fields straight away, so a password never stays in
# session state. Passwords are never put in the URL or logged. The outcome is
# kept as a translation key in st.session_state.auth_message for display.


def log_in(user_id):
    """Start a session for this user, with an empty draft."""
    switch_user(user_id)


def log_out():
    """End the session: forget the user and everything they had on screen (not the language)."""
    st.session_state.current_user = None
    set_draft(draft_ops.empty_receipt())
    set_purchase_date(date.today())
    st.session_state.flash = None


def render_login_page():
    """Shown instead of the app when nobody is logged in: log in or create an account."""
    st.write(t("login_intro", lang()))
    tab_login, tab_register = st.tabs([t("login_tab", lang()), t("register_tab", lang())])
    with tab_login:
        render_login_form()
    with tab_register:
        render_register_form()


def set_auth_message(form, key, **params):
    """Remember a message for the login or register form, shown on the next draw."""
    st.session_state.auth_message = (form, key, params)


def show_auth_message(form):
    message = st.session_state.get("auth_message")
    if message and message[0] == form:
        _, key, params = message
        if "action" in params:  # database error: translate the action too
            params = {**params, "action": t(params["action"], lang())}
        st.error(t(key, lang(), **params))
        st.session_state.auth_message = None


def take_password(key):
    """Read a password field and empty it at once (callbacks only)."""
    password = st.session_state.get(key, "")
    st.session_state[key] = ""
    return password


def on_login_submit():
    name = st.session_state.get("login_name", "")
    password = take_password("login_password")
    try:
        user = auth.authenticate(name, password)
    except auth.LoginLocked as locked:
        set_auth_message("login", "login_locked", seconds=locked.seconds_left)
        return
    except sqlite3.Error:
        logger.exception("Database error while trying to %s", t("action_log_in", "en"))
        set_auth_message("login", "write_failed", action="action_log_in")
        return
    if user is None:
        # The same message for an unknown name and a wrong password.
        set_auth_message("login", "login_failed")
        return
    log_in(user.id)


def on_register_submit():
    name = st.session_state.get("register_name", "")
    password = take_password("register_password")
    repeated = take_password("register_password_repeat")
    if password != repeated:
        set_auth_message("register", "passwords_differ")
        return
    try:
        user = auth.register(name, password, DEFAULT_CATEGORIES[lang()])
    except auth.InvalidPassword as error:
        set_auth_message("register", error.problem.key, **error.problem.params)
        return
    except db.UserNameError as error:
        params = {key: escape_markdown(value) for key, value in error.params.items()}
        set_auth_message("register", error.key, **params)
        return
    except sqlite3.Error:
        logger.exception("Database error while trying to %s", t("action_create_user", "en"))
        set_auth_message("register", "write_failed", action="action_create_user")
        return
    log_in(user.id)


def render_login_form():
    with st.form("login_form"):
        st.text_input(t("user_name_label", lang()), max_chars=MAX_NAME_LENGTH, key="login_name")
        st.text_input(
            t("password_label", lang()), type="password", max_chars=MAX_PASSWORD_LENGTH,
            autocomplete="current-password", key="login_password",
        )
        st.form_submit_button(t("log_in_button", lang()), key="login_submit", on_click=on_login_submit)
    show_auth_message("login")


def render_register_form():
    with st.form("register_form"):
        st.text_input(t("user_name_label", lang()), max_chars=MAX_NAME_LENGTH, key="register_name")
        st.text_input(
            t("password_label", lang()), type="password", max_chars=MAX_PASSWORD_LENGTH,
            autocomplete="new-password", key="register_password",
        )
        st.text_input(
            t("repeat_password_label", lang()), type="password", max_chars=MAX_PASSWORD_LENGTH,
            autocomplete="new-password", key="register_password_repeat",
        )
        st.form_submit_button(
            t("create_account_button", lang()), key="register_submit", on_click=on_register_submit
        )
    show_auth_message("register")


def on_delete_account_submit():
    password = take_password("delete_password")
    if not st.session_state.get("delete_confirm"):
        set_auth_message("delete", "delete_confirm_required")
        return
    try:
        deleted = auth.delete_account(st.session_state.current_user, password)
    except auth.LoginLocked as locked:
        set_auth_message("delete", "login_locked", seconds=locked.seconds_left)
        return
    except sqlite3.Error:
        logger.exception("Database error while trying to %s", t("action_delete_account", "en"))
        set_auth_message("delete", "write_failed", action="action_delete_account")
        return
    if not deleted:
        set_auth_message("delete", "delete_wrong_password")
        return
    log_out()
    flash("success", t("account_deleted", lang()))  # after log_out, which clears the flash


def render_delete_account_form():
    """Delete the logged-in user and all their data, confirmed with the password."""
    with st.expander(t("delete_account_header", lang())):
        st.warning(t("delete_account_warning", lang()))
        with st.form("delete_account_form"):
            st.text_input(
                t("password_label", lang()), type="password", max_chars=MAX_PASSWORD_LENGTH,
                autocomplete="current-password", key="delete_password",
            )
            st.checkbox(t("delete_confirm_label", lang()), key="delete_confirm")
            st.form_submit_button(
                t("delete_account_button", lang()), type="primary",
                key="delete_account_submit", on_click=on_delete_account_submit,
            )
        show_auth_message("delete")


def render_account_sidebar(user):
    """Who is logged in, a button to log out, and the form to delete the account."""
    with st.sidebar:
        st.caption(t("logged_in_as", lang(), name=escape_markdown(user.name)))
        if st.button(t("log_out_button", lang()), key="log_out"):
            log_out()
            st.rerun()
        render_delete_account_form()


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
                    kind, message = add_category(user_id, new_category)
                    if kind == "success":
                        flash(kind, message)
                        st.rerun()
                    st.error(message)

        with col_delete:
            removable = [c for c in categories if c != FALLBACK_CATEGORY]
            with st.form("delete_category_form"):
                to_delete = st.selectbox(t("category_to_remove", lang()), options=removable)
                st.caption(t("remove_category_note", lang()))
                st.checkbox(t("remove_category_confirm", lang()), key="category_remove_confirm")
                delete_clicked = st.form_submit_button(
                    t("remove_button", lang()), on_click=take_confirmation, args=("category_remove_confirm",)
                )
            confirmed = st.session_state.pop("confirmed_category_remove_confirm", False)
            if delete_clicked and to_delete and not confirmed:
                st.error(t("tick_to_confirm", lang()))
            elif delete_clicked and to_delete:
                with write_errors("action_remove_category"):
                    kind, message = remove_category(user_id, to_delete)
                    if kind == "success":
                        flash(kind, message)
                        st.rerun()
                    st.error(message)


def add_category(user_id, name):
    """Add a category for the user; returns (kind, message) to show. Run it inside write_errors.

    Used by "Manage categories" and by the review popup, so both follow the
    same rules (db.add_category: length, no duplicates, no reserved names).
    """
    if db.add_category(user_id, name):
        return "success", t("category_added", lang(), name=escape_markdown(name.strip()))
    return "error", t("category_name_invalid", lang(), max=MAX_NAME_LENGTH)


def take_confirmation(key):
    """Read a confirmation box and untick it at once (form submit callback).

    The value is kept in "confirmed_<key>" for this run only, so a ticked
    box never carries over to the next removal.
    """
    st.session_state[f"confirmed_{key}"] = st.session_state.get(key, False)
    st.session_state[key] = False


def remove_category(user_id, name):
    """Remove one of the user's categories; returns (kind, message) to show. Run it inside write_errors.

    Used by "Manage categories" and by the review popup. db.delete_category
    also forgets the remembered choices pointing at it and refuses the
    fallback category; saved purchases keep it.
    """
    if db.delete_category(user_id, name):
        # Rows of the unsaved receipt in that category show the fallback category now.
        set_draft(draft_ops.clear_category(st.session_state.receipt_df, name))
        return "success", t("category_removed", lang(), name=escape_markdown(name))
    return "error", t("category_not_removed", lang(), name=escape_markdown(name))


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
                format=PRICE_INPUT_FORMAT,
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
    """Upload a Kivra receipt copy, parse it and pre-fill categories from memory."""
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
        notice = import_message(result)
        flash(*notice)
        if result.remembered < len(result.items):
            # Some items got no category from memory: open the review popup by
            # itself (adding items by hand does not, see render_review). The
            # popup covers the flash, so it shows the import message itself.
            start_review()
            st.session_state.review_notice = notice
    st.rerun()


def import_message(result):
    """(kind, text) shown after a receipt PDF has been imported.

    A warning instead of a success when the items do not add up to the
    receipt's paid total, so missing or misread items are noticed.
    """
    parts = [t("import_added", lang(), count=len(result.items), remembered=result.remembered)]
    if result.purchase_date:
        parts.append(t("import_date_set", lang(), date=f"{result.purchase_date:%Y-%m-%d}"))
    else:
        parts.append(t("import_no_date", lang()))
    if paid_difference(result.items, result.paid_total) is None:
        return "success", " ".join(parts)
    parts.append(t(
        "import_total_mismatch", lang(),
        items_total=format_amount(total_cost(result.items), lang()),
        paid_total=format_amount(result.paid_total, lang()),
    ))
    return "warning", " ".join(parts)


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
                format=PRICE_INPUT_FORMAT,
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
                saved = receipts.save_receipt(
                    user_id, purchase_date, draft, st.session_state.review_kept_fallback
                )
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


# --- Review of items without a category ------------------------------------
# Items that still need a category are gone through in a popup (st.dialog),
# one item at a time: clicking a category tag chooses it and moves on. It
# opens by itself after a PDF upload that left items without a category
# (render_pdf_upload), not when items are added by hand (the form defaults to
# the fallback category, so it would open after every item). Above the table
# a button opens the popup and says how many items are left.
# review_active keeps the popup open across reruns; closing it (Stop or the
# window's X) puts the items left in review_dismissed, so it is not opened by
# itself again for them. review_handled lists the items dealt with in this
# review (given a category, kept in the fallback category on purpose, or
# skipped); review_skipped is the subset that was skipped. review_kept_fallback
# lists items put in the fallback category on purpose: only those are
# remembered as such when the receipt is saved, so items nobody decided on are
# asked about again next time. review_names are the items the open popup is
# about, for the close callback. review_notice is the PDF import message,
# shown at the top of a popup that opened by itself (it covers the flash).


def start_review():
    st.session_state.review_active = True
    st.session_state.review_handled = []
    st.session_state.review_skipped = []
    st.session_state.review_notice = None
    st.session_state.review_category_message = None


def close_review():
    """Stop or the popup's X: keep what was chosen, and do not open by itself for the items left."""
    st.session_state.review_active = False
    st.session_state.review_dismissed = st.session_state.review_names


def review_choose(name, shown):
    """Give the item the category whose label was clicked in the popup."""
    category = category_value(shown, lang())
    set_draft(draft_ops.set_item_category(st.session_state.receipt_df, name, category))
    st.session_state.review_handled.append(name)
    if category == FALLBACK_CATEGORY:
        st.session_state.review_kept_fallback.append(name)  # a choice: remember it on save


def review_skip(name):
    st.session_state.review_handled.append(name)
    st.session_state.review_skipped.append(name)


def render_review(user_id, categories):
    """The button that opens the review popup, and the popup while it is open."""
    memory = load(db.load_memory, user_id, what="what_memory")
    names = [
        name for name in draft_ops.uncategorized_items(st.session_state.receipt_df, memory, categories)
        if name not in st.session_state.review_kept_fallback  # put in the fallback category on purpose
    ]
    st.session_state.review_names = names

    if st.session_state.review_active:
        pending = [name for name in names if name not in st.session_state.review_handled]
        if pending:
            open_review_dialog(user_id, pending, categories)
        else:
            finish_review(names)
    if names and not st.session_state.review_active:
        st.button(
            t("review_open_button", lang(), count=len(names)),
            key="review_open", on_click=start_review,
        )


def finish_review(names):
    """Every item was dealt with: close the popup and say how it went."""
    st.session_state.review_active = False
    st.session_state.review_dismissed = names
    skipped = [name for name in st.session_state.review_skipped if name in names]
    if skipped:
        flash("info", t("review_done_skipped", lang(), count=len(skipped)))
    else:
        flash("success", t("review_done", lang()))
    st.rerun()


def open_review_dialog(user_id, pending, categories):
    """Show the popup for the first item that is left."""
    handled = len(st.session_state.review_handled)
    total = handled + len(pending)
    name = pending[0]
    widget_key = f"review_category_{handled + 1}"  # a new widget per item, so no choice carries over

    @st.dialog(t("review_title", lang()), width="large", on_dismiss=close_review)
    def review_dialog():
        if st.session_state.review_notice:  # what the PDF upload found, e.g. a Betalat mismatch
            kind, message = st.session_state.review_notice
            getattr(st, kind)(message)
        st.progress(handled / total, text=t("review_position", lang(), position=handled + 1, total=total))
        with st.container(border=True):
            col_name, col_amount = st.columns([3, 1], vertical_alignment="center")
            col_name.markdown(f"**{escape_markdown(name)}**")
            col_amount.markdown(format_amount(draft_ops.item_total(st.session_state.receipt_df, name), lang()))
        chosen = st.pills(
            t("review_choose_label", lang()),
            options=[category_label(category, lang()) for category in categories],
            selection_mode="single",
            key=widget_key,
        )
        with st.form("review_add_category", clear_on_submit=True, border=False):
            col_name, col_add = st.columns([3, 1], vertical_alignment="bottom")
            new_category = col_name.text_input(
                t("new_category", lang()), max_chars=MAX_NAME_LENGTH, key="review_new_category"
            )
            added = col_add.form_submit_button(t("add_button", lang()), key="review_add_submit")
        with st.expander(t("review_remove_header", lang())):
            st.caption(t("remove_category_note", lang()))
            with st.form("review_remove_category", border=False):
                to_remove = st.selectbox(
                    t("category_to_remove", lang()),
                    options=[category for category in categories if category != FALLBACK_CATEGORY],
                    key="review_remove_choice",
                )
                st.checkbox(t("remove_category_confirm", lang()), key="review_remove_confirm")
                removed = st.form_submit_button(
                    t("remove_button", lang()), key="review_remove_submit",
                    on_click=take_confirmation, args=("review_remove_confirm",),
                )
            confirmed = st.session_state.pop("confirmed_review_remove_confirm", False)
        if st.session_state.review_category_message:  # from the previous run, shown once
            kind, message = st.session_state.review_category_message
            st.session_state.review_category_message = None
            getattr(st, kind)(message)
        col_skip, col_stop = st.columns(2)
        skipped = col_skip.button(t("review_skip_button", lang()), key="review_skip")
        stopped = col_stop.button(t("review_stop_button", lang()), key="review_stop")
        # Clicks inside a dialog only rerun the dialog. A full rerun (st.rerun)
        # moves the popup to the next item and updates the table behind it.
        if chosen is not None:
            review_choose(name, chosen)
            st.rerun()
        if skipped:
            review_skip(name)
            st.rerun()
        if stopped:
            close_review()
            st.rerun()
        if added:
            # The new tag appears after a full rerun; the popup stays on this item.
            with write_errors("action_add_category"):
                st.session_state.review_category_message = add_category(user_id, new_category)
                st.rerun()
        if removed and to_remove:
            if not confirmed:
                st.session_state.review_category_message = ("error", t("tick_to_confirm", lang()))
                st.rerun()
            draft = st.session_state.receipt_df
            in_removed = {str(item).strip() for item, category in zip(draft["Item"], draft["Category"])
                          if category == to_remove}
            with write_errors("action_remove_category"):
                kind, message = remove_category(user_id, to_remove)
                st.session_state.review_category_message = (kind, message)
                if kind == "success":
                    # Items already given that category in this review need one again.
                    st.session_state.review_handled = [
                        name for name in st.session_state.review_handled if name not in in_removed
                    ]
                st.rerun()

    review_dialog()


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
    render_review(user_id, categories)
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
        col_count.metric(t("purchases", lang()), format_number(len(history), lang()))

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
                    "Price": st.column_config.NumberColumn(t("col_price", lang()), format=PRICE_INPUT_FORMAT),
                    "Category": st.column_config.TextColumn(t("col_category", lang())),
                },
            )

    render_delete_date(user_id)
    render_backup(user_id)


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
        params = {key: escape_markdown(value) if isinstance(value, str) else value for key, value in problem.params.items()}
        lines.append(f"- {t(problem.key, lang(), **params)}")
    if len(problems) > MAX_PROBLEMS_SHOWN:
        lines.append(f"- {t('backup_more_problems', lang(), count=len(problems) - MAX_PROBLEMS_SHOWN)}")
    return t("backup_not_imported", lang()) + "\n\n" + "\n".join(lines)


def main():
    st.set_page_config(page_title="ExpenseHandler", page_icon="🧾", layout="centered")
    init_session_state()
    sync_language_to_url()
    render_language_selector()
    st.title(t("app_title", lang()))

    try:
        load(setup_database, what="what_database")
        user_id = st.session_state.current_user
        user = load(db.get_user, user_id, what="what_selected_user") if user_id else None
    except DataUnavailable:
        return  # Nothing else can be shown without the database; "Try again" reruns.
    except db.DatabaseTooNew as error:
        # A newer version of the program wrote this file: leave it alone and say so.
        st.error(t(error.key, lang(), **error.params))
        return

    if user is None:
        if user_id is not None:
            log_out()  # the logged-in user no longer exists (e.g. deleted in another tab)
        show_flash()  # e.g. "account deleted"
        render_login_page()
        return

    render_account_sidebar(user)
    show_flash()

    tab_receipt, tab_history = st.tabs([t("tab_receipt", lang()), t("tab_history", lang())])
    with tab_receipt:
        render_section(render_current_receipt_tab)
    with tab_history:
        render_section(render_history_tab)


main()
