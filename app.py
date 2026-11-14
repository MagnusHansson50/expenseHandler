"""ExpenseHandler - Streamlit UI.

Run with: python -m streamlit run app.py
"""

import logging
import sqlite3
from datetime import date

import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from core.constants import MAX_NAME_LENGTH, MAX_PASSWORD_LENGTH
from core.i18n import DEFAULT_CATEGORIES, LANGUAGES, resolve_language, t
from core.text import escape_markdown
from integrations import db
from services import auth
from ui.common import DataUnavailable, flash, lang, load, render_section, show_flash
from ui.draft import set_draft, set_purchase_date
from ui.history import render_history_tab
from ui.receipt import render_current_receipt_tab
from ui.settings import render_settings

logger = logging.getLogger(__name__)


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
        "history_version": 0,
        "paid_total": None,
        "removed_total": 0.0,
        "imported_rows": [],
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
        "pending_category": None,
        "review_pending_category": None,
        "history_categories": [],
        "history_shown": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "language" not in st.session_state:
        # First run in this browser tab: take the language from ?lang= (if valid).
        st.session_state.language = resolve_language(st.query_params.get("lang"))


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
    st.session_state.pending_category = None
    st.session_state.history_categories = []
    set_draft(draft_ops.empty_receipt())
    set_purchase_date(date.today())


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
    st.session_state.pending_category = None
    st.session_state.history_categories = []
    set_draft(draft_ops.empty_receipt())
    set_purchase_date(date.today())
    st.session_state.flash = None


def render_login_page():
    """Shown instead of the app when nobody is logged in: log in or create an account.

    The whole page is one block, in the place where the app's tabs come after
    logging in. The run after logging in then replaces it at once. As two
    blocks (text, tabs), the app's tabs would replace the text and push the
    old login box down until the run ended.
    """
    with st.container():
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
    """Login form's submit callback: check the name and password, and log in on success.

    The password field is emptied first (take_password), so the password
    never stays in session state. A wrong password and an unknown name give
    the same message; a locked name says how long to wait. Only log_in, on
    success, sets current_user.
    """
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
    """Register form's submit callback: create the account and log in on success.

    Both password fields are emptied first (take_password). The new user
    gets the starting categories of the language selected now. Problems
    (passwords that differ or break the rules, a taken or bad name, a
    database error) are shown in the form via set_auth_message.
    """
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
    """Delete-account form's submit callback: delete the account and log out on success.

    Needs the ticked confirmation box and the password again; the password
    is checked through services.auth (so wrong attempts count towards the
    same lock as logins) and emptied from session state first.
    """
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
    """Who is logged in, a button to log out, the user's settings and the form to delete the account."""
    with st.sidebar:
        st.caption(t("logged_in_as", lang(), name=escape_markdown(user.name)))
        if st.button(t("log_out_button", lang()), key="log_out"):
            log_out()
            st.rerun()
        render_section(render_settings, user.id)  # a failed load stops only this section
        render_delete_account_form()


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
