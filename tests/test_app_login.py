"""Login, registration and logout in the UI. Only test passwords are used here."""

import pytest

from core.constants import MIN_PASSWORD_LENGTH
from services import auth
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


@pytest.fixture
def two_registered(temp_db):
    """Anna and Bo with passwords, created directly in the data layer."""
    auth.register("Anna", TEST_PASSWORD, [])
    auth.register("Bo", TEST_PASSWORD, [])


def all_visible_text(at):
    """Every label, value, option and message on the page, as one string."""
    parts = []
    for element in at.main.children.values():
        parts.append(str(element))
    for element in at.sidebar.children.values():
        parts.append(str(element))
    return "\n".join(parts)


# --- Before login --------------------------------------------------------


def test_no_user_names_are_shown_before_login(two_registered):
    at = start_app()
    text = all_visible_text(at)
    assert "Anna" not in text and "Bo" not in text
    assert not at.selectbox(key="language").options == []  # only the language selector
    assert len(at.selectbox) == 1


def test_login_with_correct_password(two_registered):
    at = start_app()
    log_in(at, "Anna")
    assert not at.exception
    assert logged_in_caption(at) == "Logged in as **Anna**"


@pytest.mark.parametrize("name, password", [("Anna", "wrong-password"), ("Nobody", TEST_PASSWORD)])
def test_wrong_password_and_unknown_user_give_the_same_message(two_registered, name, password):
    at = start_app()
    log_in(at, name, password)
    assert at.error[0].value == "Wrong user name or password."
    assert logged_in_caption(at) is None


def test_password_field_is_cleared_after_a_failed_login(two_registered):
    at = start_app()
    log_in(at, "Anna", "wrong-password")
    assert at.text_input(key="login_password").value == ""


def test_too_many_failures_lock_the_name(two_registered):
    at = start_app()
    for _ in range(MAX_FAILED_LOGINS):
        log_in(at, "Anna", "wrong-password")
    log_in(at, "Anna")  # even the right password is refused while locked
    assert at.error[0].value == "Too many failed attempts. Try again in 30 seconds."
    assert logged_in_caption(at) is None


# --- Registration --------------------------------------------------------


def test_registration_requires_matching_passwords(temp_db):
    at = start_app()
    create_user(at, "Anna", TEST_PASSWORD, repeated="something-else")
    assert at.error[0].value == "The passwords do not match."
    assert temp_db.get_users() == []


def test_registration_rejects_short_password(temp_db):
    at = start_app()
    create_user(at, "Anna", "x" * (MIN_PASSWORD_LENGTH - 1))
    assert at.error[0].value == f"The password must be at least {MIN_PASSWORD_LENGTH} characters."
    assert temp_db.get_users() == []


def test_registered_user_can_log_out_and_in_again(temp_db):
    at = start_app()
    create_user(at, "Anna")
    log_out(at)
    assert logged_in_caption(at) is None
    log_in(at, "Anna")
    assert logged_in_caption(at) == "Logged in as **Anna**"


# --- Isolation between users ---------------------------------------------


def test_another_user_never_sees_the_first_users_data(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Anna's secret coffee", 45.0)
    next(b for b in at.button if "Save" in b.label).click().run()
    add_manual_purchase(at, "Anna's unsaved tea", 30.0)
    log_out(at)

    create_user(at, "Bo")
    assert at.session_state["receipt_df"].empty
    text = all_visible_text(at)
    assert "Anna" not in text
    assert "secret coffee" not in text and "unsaved tea" not in text
    anna = temp_db.get_user_by_name("Anna").id
    bo = temp_db.get_user_by_name("Bo").id
    assert temp_db.get_history_dates(bo) == []
    assert len(temp_db.get_history_dates(anna)) == 1


def test_no_password_is_left_in_session_state_after_logging_in(temp_db):
    at = start_app()
    create_user(at, "Anna")
    log_out(at)
    log_in(at, "Anna")
    assert logged_in_caption(at) == "Logged in as **Anna**"
    for key in ("login_password", "register_password", "register_password_repeat"):
        # Either emptied by the submit callback or removed with the login form.
        assert key not in at.session_state or at.session_state[key] == ""
