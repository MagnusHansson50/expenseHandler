"""Deleting your own account from the sidebar. Only test passwords are used here."""

from services.auth import MAX_FAILED_LOGINS

from test_app import (
    TEST_PASSWORD,
    add_manual_purchase,
    create_user,
    log_in,
    log_out,
    logged_in_caption,
    start_app,
)


def delete_account(at, password=TEST_PASSWORD, confirm=True):
    at.text_input(key="delete_password").input(password)
    at.checkbox(key="delete_confirm").set_value(confirm)
    at.button(key="delete_account_submit").click().run()


def test_deleting_logs_out_and_removes_everything(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Coffee", 45.0)
    next(b for b in at.button if "Save" in b.label).click().run()
    anna = temp_db.get_user_by_name("Anna").id

    delete_account(at)

    assert not at.exception
    assert logged_in_caption(at) is None
    assert at.success[0].value == "Your account and all your receipts have been deleted."
    assert at.text_input(key="login_name") is not None  # back on the login page
    assert temp_db.get_user(anna) is None
    assert temp_db.get_history_dates(anna) == []
    assert at.session_state["receipt_df"].empty


def test_the_box_must_be_ticked(temp_db):
    at = start_app()
    create_user(at, "Anna")
    delete_account(at, confirm=False)
    assert at.error[0].value == "Tick the box to confirm that everything should be deleted."
    assert logged_in_caption(at) == "Logged in as **Anna**"
    assert temp_db.get_user_by_name("Anna") is not None


def test_wrong_password_deletes_nothing(temp_db):
    at = start_app()
    create_user(at, "Anna")
    delete_account(at, password="wrong-password")
    assert at.error[0].value == "Wrong password. The account was not deleted."
    assert logged_in_caption(at) == "Logged in as **Anna**"
    assert at.text_input(key="delete_password").value == ""
    assert temp_db.get_user_by_name("Anna") is not None


def test_too_many_wrong_passwords_lock_deleting_too(temp_db):
    at = start_app()
    create_user(at, "Anna")
    for _ in range(MAX_FAILED_LOGINS):
        delete_account(at, password="wrong-password")
    delete_account(at)  # even the right password is refused while locked
    assert at.error[0].value == "Too many failed attempts. Try again in 30 seconds."
    assert temp_db.get_user_by_name("Anna") is not None


def test_other_users_are_not_affected(temp_db):
    at = start_app()
    create_user(at, "Bo")
    add_manual_purchase(at, "Bo's tea", 30.0)
    next(b for b in at.button if "Save" in b.label).click().run()
    log_out(at)
    create_user(at, "Anna")
    delete_account(at)

    log_in(at, "Bo")
    assert logged_in_caption(at) == "Logged in as **Bo**"
    assert len(temp_db.get_history_dates(temp_db.get_user_by_name("Bo").id)) == 1


def test_the_name_can_be_registered_again(temp_db):
    at = start_app()
    create_user(at, "Anna")
    delete_account(at)
    create_user(at, "Anna")
    assert logged_in_caption(at) == "Logged in as **Anna**"


def test_no_password_is_left_in_session_state(temp_db):
    at = start_app()
    create_user(at, "Anna")
    delete_account(at, password="wrong-password")
    delete_account(at)
    # Either emptied by the submit callback or removed with the form after logging out.
    assert "delete_password" not in at.session_state or at.session_state["delete_password"] == ""
