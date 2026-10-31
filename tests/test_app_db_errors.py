"""The UI shows a message instead of crashing when the database fails.

Failures are simulated by replacing functions in integrations.db with ones
that raise sqlite3.OperationalError ("database is locked").
"""

import sqlite3

import pytest

from integrations import db
from test_app import add_manual_purchase, create_user, start_app


def locked(*_args, **_kwargs):
    raise sqlite3.OperationalError("database is locked")


def fail_once(monkeypatch, name):
    """Make db.<name> raise once, then behave normally again."""
    real = getattr(db, name)
    state = {"failed": False}

    def wrapper(*args, **kwargs):
        if not state["failed"]:
            state["failed"] = True
            raise sqlite3.OperationalError("database is locked")
        return real(*args, **kwargs)

    monkeypatch.setattr(db, name, wrapper)


@pytest.fixture
def anna_app(temp_db):
    at = start_app()
    create_user(at, "Anna")
    return at


def click(at, label_part):
    next(b for b in at.button if label_part in b.label).click().run()


def retry_buttons(at):
    return [b for b in at.button if "Try again" in b.label]


# --- Writes: message, input kept, retry works ----------------------------


def test_failed_save_keeps_the_receipt_and_retry_saves_once(anna_app, temp_db, monkeypatch):
    add_manual_purchase(anna_app, "Coffee", 45.0)
    fail_once(monkeypatch, "_write_memory")

    click(anna_app, "Save")
    assert not anna_app.exception
    assert "Could not save the receipt" in anna_app.error[0].value
    assert len(anna_app.session_state["receipt_df"]) == 1
    anna = temp_db.get_users()[0].id
    assert temp_db.get_history_dates(anna) == []

    click(anna_app, "Save")
    assert not anna_app.exception
    assert len(temp_db.get_history(anna, "2000-01-01", "2100-01-01")) == 1
    assert anna_app.session_state["receipt_df"].empty


def test_failed_create_user_shows_message(temp_db, monkeypatch):
    at = start_app()
    monkeypatch.setattr(db, "create_user", locked)
    create_user(at, "Anna")
    assert not at.exception
    assert "Could not create the user" in at.sidebar.error[0].value


def test_failed_add_category_shows_message(anna_app, monkeypatch):
    monkeypatch.setattr(db, "add_category", locked)
    next(w for w in anna_app.text_input if w.label == "New category").input("Candy")
    click(anna_app, "➕ Add")
    assert not anna_app.exception
    assert "Could not add the category" in anna_app.error[0].value


# --- Reads: message, "Try again", other parts keep working ---------------


def test_failed_history_load_shows_retry_and_receipt_tab_still_works(anna_app, monkeypatch):
    real_get_history = db.get_history
    monkeypatch.setattr(db, "get_history", locked)
    anna_app.run()

    assert not anna_app.exception
    assert any("Could not load your history" in e.value for e in anna_app.error)
    assert len(retry_buttons(anna_app)) == 1
    # The receipt tab is rendered independently of the failing history tab.
    assert any(b for b in anna_app.button if "Add to list" in b.label)

    monkeypatch.setattr(db, "get_history", real_get_history)
    retry_buttons(anna_app)[0].click().run()
    assert not anna_app.exception
    assert not retry_buttons(anna_app)
    assert any("No purchases saved in this period" in i.value for i in anna_app.info)


def test_failed_user_list_stops_page_until_retry(temp_db, monkeypatch):
    temp_db.create_user("Anna")
    real_get_users = db.get_users
    monkeypatch.setattr(db, "get_users", locked)
    at = start_app()

    assert not at.exception
    assert "Could not load the list of users" in at.sidebar.error[0].value
    assert len(at.tabs) == 0

    monkeypatch.setattr(db, "get_users", real_get_users)
    retry_buttons(at)[0].click().run()
    assert not at.exception
    assert not at.sidebar.error
    assert "Select or create a user" in at.info[0].value


def test_database_errors_are_logged_without_receipt_data(anna_app, monkeypatch, caplog):
    add_manual_purchase(anna_app, "Secret item", 45.0)
    fail_once(monkeypatch, "_write_memory")
    with caplog.at_level("ERROR"):
        click(anna_app, "Save")
    assert "Database error while trying to save the receipt" in caplog.text
    assert "Secret item" not in caplog.text
