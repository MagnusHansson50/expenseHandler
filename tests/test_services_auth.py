"""Login, registration and reset flows. Only test passwords are used here."""

import pytest

from core.constants import FALLBACK_CATEGORY, MIN_PASSWORD_LENGTH
from integrations import db
from services import auth
from services.auth import LOCK_SECONDS, MAX_FAILED_LOGINS, LoginLocked, LoginThrottle

PASSWORD = "test-password-1"


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def throttle(clock):
    return LoginThrottle(clock=clock)


@pytest.fixture
def anna(temp_db):
    return auth.register("Anna", PASSWORD, ["Mejeri"])


# --- register ------------------------------------------------------------


def test_register_creates_user_with_categories_and_password(anna, temp_db):
    assert anna.name == "Anna"
    assert sorted(temp_db.get_categories(anna.id)) == sorted(["Mejeri", FALLBACK_CATEGORY])
    login = temp_db.get_login("Anna")
    assert PASSWORD.encode() not in login.password_hash + login.salt


def test_register_rejects_short_password_and_creates_nothing(temp_db):
    with pytest.raises(auth.InvalidPassword) as caught:
        auth.register("Anna", "x" * (MIN_PASSWORD_LENGTH - 1), [])
    assert caught.value.problem.key == "password_too_short"
    assert temp_db.get_users() == []


def test_register_rejects_taken_name(anna):
    with pytest.raises(db.UserNameTaken):
        auth.register("Anna", "another-password", [])


# --- authenticate --------------------------------------------------------


def test_correct_password_logs_in(anna, throttle):
    assert auth.authenticate("Anna", PASSWORD, throttle) == anna
    assert auth.authenticate("  Anna ", PASSWORD, throttle) == anna


def test_wrong_password_and_unknown_name_both_return_none(anna, throttle):
    assert auth.authenticate("Anna", "wrong-password", throttle) is None
    assert auth.authenticate("Nobody", PASSWORD, throttle) is None


def test_unknown_name_still_hashes_to_hide_which_names_exist(anna, throttle, monkeypatch):
    calls = []
    real_verify = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda *a: calls.append(1) or real_verify(*a))
    auth.authenticate("Nobody", PASSWORD, throttle)
    assert calls == [1]


def test_user_without_password_cannot_log_in(temp_db, throttle):
    temp_db.create_user("NoPassword")
    assert auth.authenticate("NoPassword", "", throttle) is None
    assert auth.authenticate("NoPassword", PASSWORD, throttle) is None


# --- throttling ----------------------------------------------------------


def test_name_is_locked_after_too_many_failures(anna, throttle, clock):
    for _ in range(MAX_FAILED_LOGINS):
        assert auth.authenticate("Anna", "wrong-password", throttle) is None

    with pytest.raises(LoginLocked) as caught:
        auth.authenticate("Anna", PASSWORD, throttle)  # even the right password is refused
    assert caught.value.seconds_left == LOCK_SECONDS

    clock.now += LOCK_SECONDS - 1
    with pytest.raises(LoginLocked) as caught:
        auth.authenticate("Anna", PASSWORD, throttle)
    assert caught.value.seconds_left == 1

    clock.now += 1
    assert auth.authenticate("Anna", PASSWORD, throttle) == anna


def test_locked_name_is_not_hashed(anna, throttle, monkeypatch):
    for _ in range(MAX_FAILED_LOGINS):
        auth.authenticate("Anna", "wrong-password", throttle)
    monkeypatch.setattr(auth, "verify_password", lambda *_: pytest.fail("must not hash while locked"))
    with pytest.raises(LoginLocked):
        auth.authenticate("Anna", PASSWORD, throttle)


def test_lock_counts_name_variants_together_and_only_that_name(anna, throttle, temp_db):
    bo = auth.register("Bo", PASSWORD, [])
    for name in ["Anna", "anna", " ANNA ", "Anna", "anna"]:
        auth.authenticate(name, "wrong-password", throttle)
    with pytest.raises(LoginLocked):
        auth.authenticate("Anna", PASSWORD, throttle)
    assert auth.authenticate("Bo", PASSWORD, throttle) == bo


def test_success_resets_the_failure_count(anna, throttle):
    for _ in range(MAX_FAILED_LOGINS - 1):
        auth.authenticate("Anna", "wrong-password", throttle)
    assert auth.authenticate("Anna", PASSWORD, throttle) == anna
    for _ in range(MAX_FAILED_LOGINS - 1):
        auth.authenticate("Anna", "wrong-password", throttle)
    assert auth.authenticate("Anna", PASSWORD, throttle) == anna  # not locked


def test_unknown_names_are_throttled_too(temp_db, throttle):
    for _ in range(MAX_FAILED_LOGINS):
        auth.authenticate("Nobody", PASSWORD, throttle)
    with pytest.raises(LoginLocked):
        auth.authenticate("Nobody", PASSWORD, throttle)


# --- reset_password ------------------------------------------------------


def test_reset_password_replaces_the_old_one(anna, throttle):
    assert auth.reset_password("Anna", "new-test-password") is True
    assert auth.authenticate("Anna", PASSWORD, throttle) is None
    assert auth.authenticate("Anna", "new-test-password", throttle) == anna


def test_reset_password_gives_a_password_to_a_user_without_one(temp_db, throttle):
    user_id = temp_db.create_user("Old")
    assert auth.reset_password("Old", "new-test-password") is True
    assert auth.authenticate("Old", "new-test-password", throttle).id == user_id


def test_reset_password_for_unknown_user_or_bad_password(anna):
    assert auth.reset_password("Nobody", "new-test-password") is False
    with pytest.raises(auth.InvalidPassword):
        auth.reset_password("Anna", "short")
