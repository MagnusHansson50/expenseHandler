"""The UI shows a message instead of crashing when the database fails.

Failures are simulated by replacing functions in integrations.db with ones
that raise sqlite3.OperationalError ("database is locked").
"""

import sqlite3

import pytest

from integrations import db
from test_app import add_manual_purchase, create_user, log_in, log_out, logged_in_caption, start_app


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
    monkeypatch.setattr(db, "create_user_with_password", locked)
    create_user(at, "Anna")
    assert not at.exception
    assert "Could not create the user" in at.error[0].value
    assert logged_in_caption(at) is None


def test_failed_login_lookup_shows_message(temp_db, monkeypatch):
    at = start_app()
    create_user(at, "Anna")
    log_out(at)
    monkeypatch.setattr(db, "get_login", locked)
    log_in(at, "Anna")
    assert not at.exception
    assert "Could not log in" in at.error[0].value
    assert logged_in_caption(at) is None


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


def test_failed_user_load_stops_page_until_retry(anna_app, monkeypatch):
    real_get_user = db.get_user
    monkeypatch.setattr(db, "get_user", locked)
    anna_app.run()

    assert not anna_app.exception
    assert "Could not load the selected user" in anna_app.error[0].value
    assert len(anna_app.tabs) == 0

    monkeypatch.setattr(db, "get_user", real_get_user)
    retry_buttons(anna_app)[0].click().run()
    assert not anna_app.exception
    assert logged_in_caption(anna_app) == "Logged in as **Anna**"


def test_database_errors_are_logged_without_receipt_data(anna_app, monkeypatch, caplog):
    add_manual_purchase(anna_app, "Secret item", 45.0)
    fail_once(monkeypatch, "_write_memory")
    with caplog.at_level("ERROR"):
        click(anna_app, "Save")
    assert "Database error while trying to save the receipt" in caplog.text
    assert "Secret item" not in caplog.text
