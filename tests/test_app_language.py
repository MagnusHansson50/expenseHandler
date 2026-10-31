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
    at = run_app("en")
    create_user(at, "Anna")
    add_manual_purchase(at, "Coffee", 45.0)  # uses the English labels

    language_box(at).set_value("sv").run()
    assert not at.exception
    assert at.session_state["current_user"] is not None
    assert at.session_state["receipt_df"].to_dict("records") == [
        {"Item": "Coffee", "Price": 45.0, "Category": "Other"}
    ]


# --- The UI in Swedish ---------------------------------------------------


def test_main_screens_in_swedish(temp_db):
    at = run_app("sv")
    assert "Välj eller skapa en användare" in at.info[0].value
    assert at.sidebar.header[0].value == "👤 Användare"

    create_user(at, "Anna")
    assert at.caption[0].value == "Visar data för **Anna**"
    assert [tab.label for tab in at.tabs] == ["🛒 Aktuellt kvitto", "📜 Historik"]
    assert any("Lägg till ett köp manuellt" in i.value for i in at.info)


def test_swedish_messages_and_amounts(temp_db):
    at = run_app("sv")
    create_user(at, "Anna")
    next(w for w in at.text_input if w.label == "Vara").input("Kaffe")
    next(w for w in at.number_input if w.label == "Pris (kr)").set_value(1234.5)
    next(b for b in at.button if "Lägg till i listan" in b.label).click().run()

    assert at.metric[0].label == "Totalt"
    assert at.metric[0].value == "1 234,50 kr"

    next(b for b in at.button if "Spara" in b.label).click().run()
    assert not at.exception
    assert at.success[0].value.startswith("1 rader sparades för ")


def test_same_screen_in_english_uses_english_amounts(temp_db):
    at = run_app("en")
    create_user(at, "Anna")
    next(w for w in at.text_input if w.label == "Item").input("Coffee")
    next(w for w in at.number_input if w.label == "Price (kr)").set_value(1234.5)
    next(b for b in at.button if "Add to list" in b.label).click().run()
    assert at.metric[0].value == "1,234.50 kr"


def test_user_name_errors_are_translated(temp_db):
    at = run_app("sv")
    create_user(at, "Anna")
    create_user(at, "Anna")
    assert at.sidebar.error[0].value == "Det finns redan en användare som heter 'Anna'."

    language_box(at).set_value("en").run()
    create_user(at, "Anna")
    assert at.sidebar.error[0].value == "A user named 'Anna' already exists."


def test_save_problems_are_translated(temp_db):
    import pandas as pd

    from core.constants import MAX_PRICE

    at = run_app("sv")
    create_user(at, "Anna")
    # The UI blocks out-of-range prices, so put an invalid draft straight into session state.
    at.session_state["receipt_df"] = pd.DataFrame(
        [{"Item": "TV", "Price": MAX_PRICE + 1.0, "Category": "Other"}]
    )
    at.run()
    next(b for b in at.button if "Spara" in b.label).click().run()

    assert not at.exception
    assert at.error[0].value == (
        f"Kvittot sparades inte:\n\n- Rad 1: priset måste vara mellan -{MAX_PRICE} och {MAX_PRICE} kr."
    )
