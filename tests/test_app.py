"""Headless tests of the Streamlit UI with AppTest, against a temporary database.

PDF upload and st.data_editor interactions are not supported by AppTest;
their logic is covered in test_receipt.py and test_parser.py.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app(temp_db):
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def create_user(at, name):
    at.sidebar.text_input[0].input(name)
    at.sidebar.button[0].click().run()


def widget(widgets, label):
    return next(w for w in widgets if w.label == label)


def add_manual_purchase(at, item, price):
    widget(at.text_input, "Item").input(item)
    widget(at.number_input, "Price (kr)").set_value(price)
    next(b for b in at.button if "Add to list" in b.label).click().run()


def test_nothing_but_sidebar_until_user_selected(app):
    assert not app.exception
    assert "Select or create a user" in app.info[0].value
    assert len(app.tabs) == 0


def test_create_user_selects_it(app):
    create_user(app, "Anna")
    assert not app.exception
    assert "Anna" in app.caption[0].value
    assert len(app.tabs) == 2


def test_manual_purchase_is_added_and_saved(app, temp_db):
    create_user(app, "Anna")
    add_manual_purchase(app, "Coffee", 45.0)
    assert app.session_state["receipt_df"].to_dict("records") == [
        {"Item": "Coffee", "Price": 45.0, "Category": "Other"}
    ]

    next(b for b in app.button if "Save" in b.label).click().run()
    assert not app.exception
    anna = temp_db.get_users()[0][0]
    assert temp_db.get_history_dates(anna)
    assert temp_db.load_memory(anna) == {"Coffee": "Other"}
    assert app.session_state["receipt_df"].empty


def test_switching_user_clears_unsaved_receipt(app):
    create_user(app, "Anna")
    add_manual_purchase(app, "Coffee", 45.0)
    create_user(app, "Bo")
    assert "Bo" in app.caption[0].value
    assert app.session_state["receipt_df"].empty


def test_removing_category_in_ui_forgets_its_memory(app, temp_db):
    create_user(app, "Anna")
    anna = temp_db.get_users()[0][0]
    temp_db.save_memory(anna, {"Chips": "Snacks"})

    widget(app.selectbox, "Category to remove").set_value("Snacks")
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert not app.exception
    assert "Removed category 'Snacks'" in app.success[0].value
    assert "Snacks" not in temp_db.get_categories(anna)
    assert temp_db.load_memory(anna) == {}


def tabs_position(at):
    """Index of the top-level block holding the tabs in the main area."""
    return next(
        index
        for index, child in at.main.children.items()
        if any(type(node).__name__ == "Tab" for node in getattr(child, "children", {}).values())
    )


def test_tabs_keep_their_position_when_a_flash_message_comes_and_goes(app):
    # If the tabs move, Streamlit treats them as new and jumps back to the first tab.
    create_user(app, "Anna")
    without_message = tabs_position(app)

    widget(app.selectbox, "Category to remove").set_value("Snacks")
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert app.success  # flash message is showing
    assert tabs_position(app) == without_message

    app.run()
    assert not app.success  # flash message is gone
    assert tabs_position(app) == without_message


# At most MAX_NAME_LENGTH (50) characters, so the sidebar field accepts it.
MARKDOWN_NAME = "E ![x](http://e.test/p.png) [C](https://e.test)"
WJ = "\u2060"  # invisible WORD JOINER inserted to stop automatic links
ESCAPED_NAME = rf"E \!\[x\]\(http\:{WJ}\/\/e\.test\/p\.png\) \[C\]\(https\:{WJ}\/\/e\.test\)"


def test_user_name_is_shown_literally_not_as_markdown(app):
    create_user(app, MARKDOWN_NAME)
    assert app.caption[0].value == f"Showing data for **{ESCAPED_NAME}**"


def test_duplicate_user_error_shows_name_literally(app):
    create_user(app, MARKDOWN_NAME)
    create_user(app, MARKDOWN_NAME)
    assert ESCAPED_NAME in app.sidebar.error[0].value


def test_category_names_in_messages_are_shown_literally(app):
    create_user(app, "Anna")
    widget(app.text_input, "New category").input("**Bold** [x](https://evil.test)")
    next(b for b in app.button if b.label == "➕ Add").click().run()
    assert app.success[0].value == (
        rf"Added category '\*\*Bold\*\* \[x\]\(https\:{WJ}\/\/evil\.test\)'."
    )

    widget(app.selectbox, "Category to remove").set_value("**Bold** [x](https://evil.test)")
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert app.success[0].value == (
        rf"Removed category '\*\*Bold\*\* \[x\]\(https\:{WJ}\/\/evil\.test\)'."
    )


def test_fallback_category_cannot_be_chosen_for_removal(app):
    create_user(app, "Anna")
    options = widget(app.selectbox, "Category to remove").options
    assert "Other" not in options
    assert "Dairy" in options
