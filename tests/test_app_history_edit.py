"""Changing the category of saved purchases in the History tab.

AppTest cannot edit cells in st.data_editor, so these tests check the list's
setup (only the category is editable, a selectbox of the user's categories)
and the save button; picking a category in the table is checked in a browser.
The logic behind it is tested in test_history.py and test_db_update_categories.py.
"""

import json
from datetime import date

import pandas as pd
import pytest

from test_app import create_user, start_app


@pytest.fixture
def anna_with_history(temp_db):
    at = start_app()
    create_user(at, "Anna")
    anna = temp_db.get_users()[0].id
    temp_db.save_receipt(
        anna, date.today(),
        pd.DataFrame([("Milk", 15.9, "Drinks"), ("Chips", 25.0, "Other")], columns=["Item", "Price", "Category"]),
        {},
    )
    at.run()
    return at, anna


def history_editor(at):
    def walk(node):
        yield node
        for child in getattr(node, "children", {}).values():
            yield from walk(child)

    return next(node for node in walk(at._tree) if str(getattr(node, "key", "")).startswith("history_editor_"))


def editor_columns(at):
    """Column settings of the history editor, as Streamlit sends them to the browser."""
    return json.loads(history_editor(at).proto.columns)


def test_only_the_category_can_be_changed(anna_with_history):
    at, _ = anna_with_history
    columns = editor_columns(at)
    assert columns["Date"]["disabled"] and columns["Item"]["disabled"] and columns["Price"]["disabled"]
    assert not columns["Category"].get("disabled")
    assert history_editor(at).proto.editing_mode == history_editor(at).proto.EditingMode.FIXED  # no new rows


def test_the_category_list_holds_the_users_categories_as_labels(anna_with_history, temp_db):
    at, anna = anna_with_history
    options = editor_columns(at)["Category"]["type_config"]["options"]
    assert sorted(options) == sorted(temp_db.get_categories(anna))  # English: "Other" is shown as "Other"
    assert list(history_editor(at).proto.column_order) == ["Date", "Item", "Price", "Category"]  # no Id


def test_a_database_error_is_shown_and_nothing_is_lost(anna_with_history, temp_db, monkeypatch):
    import sqlite3

    from services import history

    def locked(*_args):
        raise sqlite3.OperationalError("database is locked")

    at, anna = anna_with_history
    monkeypatch.setattr(history, "change_categories", locked)
    at.button(key="history_save").click().run()
    assert not at.exception
    assert "Could not save the changed categories" in at.error[0].value
    assert temp_db.get_all_history(anna)["Category"].tolist() == ["Drinks", "Other"]


def test_saving_without_changes_says_so(anna_with_history, temp_db):
    at, anna = anna_with_history
    at.button(key="history_save").click().run()
    assert not at.exception
    assert at.info[0].value == "No category was changed."
    assert temp_db.get_all_history(anna)["Category"].tolist() == ["Drinks", "Other"]
