"""Helpers every part of the UI uses: the language, database error handling, flash messages
and the callbacks of confirm-and-remove forms.
"""

import logging
import sqlite3
from contextlib import contextmanager

import streamlit as st

from core.i18n import t

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


# --- Language --------------------------------------------------------------
# The language lives in st.session_state.language and in the URL (?lang=sv),
# so it survives a page reload and can be bookmarked. It is not stored per user.


def lang():
    """The language currently selected in this browser tab."""
    return st.session_state.language


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


def take_confirmation(key):
    """Read a confirmation box and untick it at once (form submit callback).

    The value is kept in "confirmed_<key>" for this run only, so a ticked
    box never carries over to the next removal.
    """
    st.session_state[f"confirmed_{key}"] = st.session_state.get(key, False)
    st.session_state[key] = False


def take_removal(confirm_key, choice_key):
    """Submit callback of a remove form: keep the confirmation and the chosen option.

    The choice must be read here, in the callback, with the value the user
    sent. In the run that follows, Streamlit checks the select box against
    its options again: if the chosen category or date was removed in another
    tab meanwhile, it silently returns the FIRST option instead, and that
    one would be removed. The chosen value is kept in "chosen_<choice_key>"
    for this run only.
    """
    take_confirmation(confirm_key)
    st.session_state[f"chosen_{choice_key}"] = st.session_state.get(choice_key)
