"""Headless tests of the Streamlit UI with AppTest, against a temporary database.

PDF upload and st.data_editor interactions are not supported by AppTest;
their logic is covered in test_receipt.py and test_parser.py.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def start_app(lang="en"):
    """Run the app headless in the given language (?lang=)."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.query_params["lang"] = lang
    return at.run()


@pytest.fixture
def app(temp_db):
    return start_app()


TEST_PASSWORD = "test-password-1"


def create_user(at, name, password=TEST_PASSWORD, repeated=None):
    """Register through the "Create account" form (which also logs in)."""
    at.text_input(key="register_name").input(name)
    at.text_input(key="register_password").input(password)
    at.text_input(key="register_password_repeat").input(password if repeated is None else repeated)
    at.button(key="register_submit").click().run()


def log_in(at, name, password=TEST_PASSWORD):
    at.text_input(key="login_name").input(name)
    at.text_input(key="login_password").input(password)
    at.button(key="login_submit").click().run()


def log_out(at):
    at.sidebar.button(key="log_out").click().run()


def logged_in_caption(at):
    return at.sidebar.caption[0].value if at.sidebar.caption else None


def widget(widgets, label):
    return next(w for w in widgets if w.label == label)


def add_manual_purchase(at, item, price):
    widget(at.text_input, "Item").input(item)
    widget(at.number_input, "Price (kr)").set_value(price)
    next(b for b in at.button if "Add to list" in b.label).click().run()


def test_only_the_login_page_is_shown_until_logged_in(app):
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["🔐 Log in", "➕ Create account"]
    assert not any("Add to list" in b.label for b in app.button)
    assert logged_in_caption(app) is None


def test_registering_logs_in(app):
    create_user(app, "Anna")
    assert not app.exception
    assert logged_in_caption(app) == "Logged in as **Anna**"
    assert [tab.label for tab in app.tabs] == ["🛒 Current Receipt", "📜 History"]


def test_manual_purchase_is_added_and_saved(app, temp_db):
    create_user(app, "Anna")
    add_manual_purchase(app, "Coffee", 45.0)
    assert app.session_state["receipt_df"].to_dict("records") == [
        {"Item": "Coffee", "Price": 45.0, "Category": "Other"}
    ]

    next(b for b in app.button if "Save" in b.label).click().run()
    assert not app.exception
    anna = temp_db.get_users()[0].id
    assert temp_db.get_history_dates(anna)
    # "Other" was only the form's default, not a choice: not remembered, asked about next time.
    assert temp_db.load_memory(anna) == {}
    assert app.session_state["receipt_df"].empty


def test_logging_out_clears_the_unsaved_receipt(app):
    create_user(app, "Anna")
    add_manual_purchase(app, "Coffee", 45.0)
    log_out(app)
    assert app.session_state["current_user"] is None
    assert app.session_state["receipt_df"].empty
    assert logged_in_caption(app) is None

    create_user(app, "Bo")
    assert logged_in_caption(app) == "Logged in as **Bo**"
    assert app.session_state["receipt_df"].empty


def test_removing_category_in_ui_forgets_its_memory(app, temp_db):
    create_user(app, "Anna")
    anna = temp_db.get_users()[0].id
    temp_db.save_memory(anna, {"Chips": "Snacks"})

    widget(app.selectbox, "Category to remove").set_value("Snacks")
    app.checkbox(key="category_remove_confirm").check()
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert not app.exception
    assert "Removed category 'Snacks'" in app.success[0].value
    assert "Snacks" not in temp_db.get_categories(anna)
    assert temp_db.load_memory(anna) == {}


def test_the_box_is_unticked_again_after_removing(app, temp_db):
    create_user(app, "Anna")
    widget(app.selectbox, "Category to remove").set_value("Snacks")
    app.checkbox(key="category_remove_confirm").check()
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert app.checkbox(key="category_remove_confirm").value is False
    next(b for b in app.button if "Remove" in b.label).click().run()  # the next category, not confirmed
    assert app.error[0].value == "Tick the box to confirm."


def test_removing_a_category_needs_the_box_ticked(app, temp_db):
    create_user(app, "Anna")
    widget(app.selectbox, "Category to remove").set_value("Snacks")
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert app.error[0].value == "Tick the box to confirm."
    assert "Snacks" in temp_db.get_categories(temp_db.get_users()[0].id)


def test_unsaved_items_in_a_removed_category_move_to_other(app, temp_db):
    create_user(app, "Anna")
    widget(app.text_input, "Item").input("Shoes")
    widget(app.number_input, "Price (kr)").set_value(499.0)
    widget(app.selectbox, "Category").set_value("Snacks")
    next(b for b in app.button if "Add to list" in b.label).click().run()
    assert app.session_state["receipt_df"]["Category"].tolist() == ["Snacks"]

    widget(app.selectbox, "Category to remove").set_value("Snacks")
    app.checkbox(key="category_remove_confirm").check()
    next(b for b in app.button if "Remove" in b.label).click().run()

    assert app.session_state["receipt_df"]["Category"].tolist() == ["Other"]
    assert next(b.label for b in app.button if b.key == "review_open") == "🏷️ Go through items without a category (1)"


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
    app.checkbox(key="category_remove_confirm").check()
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
    assert logged_in_caption(app) == f"Logged in as **{ESCAPED_NAME}**"


def test_duplicate_user_error_shows_name_literally(app):
    create_user(app, MARKDOWN_NAME)
    log_out(app)
    create_user(app, MARKDOWN_NAME)
    assert ESCAPED_NAME in app.error[0].value


def test_category_names_in_messages_are_shown_literally(app):
    create_user(app, "Anna")
    widget(app.text_input, "New category").input("**Bold** [x](https://evil.test)")
    next(b for b in app.button if b.label == "➕ Add").click().run()
    assert app.success[0].value == (
        rf"Added category '\*\*Bold\*\* \[x\]\(https\:{WJ}\/\/evil\.test\)'."
    )

    widget(app.selectbox, "Category to remove").set_value("**Bold** [x](https://evil.test)")
    app.checkbox(key="category_remove_confirm").check()
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert app.success[0].value == (
        rf"Removed category '\*\*Bold\*\* \[x\]\(https\:{WJ}\/\/evil\.test\)'."
    )


def test_fallback_category_cannot_be_chosen_for_removal(app):
    create_user(app, "Anna")
    options = widget(app.selectbox, "Category to remove").options
    assert "Other" not in options
    assert "Dairy" in options


def test_removing_a_category_already_removed_elsewhere_says_so(app, temp_db):
    create_user(app, "Anna")
    widget(app.selectbox, "Category to remove").set_value("Snacks")
    temp_db.delete_category(temp_db.get_users()[0].id, "Snacks")  # as another tab could
    app.checkbox(key="category_remove_confirm").check()
    next(b for b in app.button if "Remove" in b.label).click().run()
    assert app.error[0].value == "Category 'Snacks' no longer exists; it may have been removed in another tab."


def test_deleting_a_date_already_deleted_elsewhere_never_deletes_another_date(app, temp_db):
    import pandas as pd

    create_user(app, "Anna")
    anna = temp_db.get_users()[0].id
    for day in ("2026-11-01", "2026-11-02"):
        temp_db.save_receipt(anna, day, pd.DataFrame([("X", 1.0, "Other")], columns=["Item", "Price", "Category"]), {})
    app.run()
    app.selectbox(key="delete_date_choice").set_value("2026-11-02")
    temp_db.delete_history_date(anna, "2026-11-02")  # as another tab could
    app.checkbox(key="delete_date_confirm").check()
    next(b for b in app.button if b.label == "Delete").click().run()
    assert temp_db.get_history_dates(anna) == ["2026-11-01"]  # the other date is untouched
    assert app.info[0].value == (
        "No purchases are saved on 2026-11-02 any more; they may have been deleted in another tab."
    )
