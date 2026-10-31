"""Language selection in the UI: default, ?lang= in the URL, switching."""

import pytest
from streamlit.testing.v1 import AppTest

from core.i18n import DEFAULT_LANGUAGE
from test_app import APP_PATH, add_manual_purchase, create_user


def run_app(lang_param=None):
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    if lang_param is not None:
        at.query_params["lang"] = lang_param
    return at.run()


def language_box(at):
    return at.sidebar.selectbox(key="language")


def url_language(at):
    """?lang= as seen by AppTest (it may hold a string or a one-item list)."""
    value = at.query_params["lang"]
    return value[0] if isinstance(value, list) else value


def test_default_language_is_swedish_and_written_to_url(temp_db):
    at = run_app()
    assert not at.exception
    assert language_box(at).value == DEFAULT_LANGUAGE == "sv"
    assert language_box(at).label == "🌐 Språk"
    assert url_language(at) == "sv"


def test_language_is_taken_from_url(temp_db):
    at = run_app("en")
    assert language_box(at).value == "en"
    assert language_box(at).label == "🌐 Language"


@pytest.mark.parametrize("bad", ["de", "", "sv-SE", "<script>"])
def test_unknown_language_in_url_falls_back_to_default(temp_db, bad):
    at = run_app(bad)
    assert not at.exception
    assert language_box(at).value == DEFAULT_LANGUAGE
    assert url_language(at) == DEFAULT_LANGUAGE


def test_switching_language_updates_label_and_url(temp_db):
    at = run_app()
    language_box(at).set_value("en").run()
    assert not at.exception
    assert language_box(at).label == "🌐 Language"
    assert url_language(at) == "en"

    language_box(at).set_value("sv").run()
    assert language_box(at).label == "🌐 Språk"
    assert url_language(at) == "sv"


def test_switching_language_keeps_user_and_unsaved_receipt(temp_db):
    at = run_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Coffee", 45.0)

    language_box(at).set_value("en").run()
    assert not at.exception
    assert at.session_state["current_user"] is not None
    assert at.session_state["receipt_df"].to_dict("records") == [
        {"Item": "Coffee", "Price": 45.0, "Category": "Other"}
    ]
