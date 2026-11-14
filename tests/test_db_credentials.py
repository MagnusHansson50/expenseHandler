"""Credentials in the data layer. Hashes here are fake bytes; no real passwords."""

import sqlite3

import pytest

from core.constants import FALLBACK_CATEGORY
from integrations import db

HASH_A, SALT_A = b"hash-a" * 8, b"salt-a" * 2
HASH_B, SALT_B = b"hash-b" * 8, b"salt-b" * 2


def test_credentials_table_is_created_and_init_is_idempotent(temp_db):
    temp_db.init_db()
    conn = sqlite3.connect(temp_db.DB_PATH)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(credentials)")]
    assert columns == ["user_id", "password_hash", "salt"]


def test_create_user_with_password_stores_user_categories_and_hash(temp_db):
    user_id = temp_db.create_user_with_password("Anna", HASH_A, SALT_A, ["Mejeri"])
    login = temp_db.get_login("Anna")
    assert login == db.Login(db.User(user_id, "Anna"), HASH_A, SALT_A)
    assert sorted(temp_db.get_categories(user_id)) == sorted(["Mejeri", FALLBACK_CATEGORY])


def test_create_user_with_password_is_all_or_nothing(temp_db, monkeypatch):
    def failing_write(*_args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "_write_password", failing_write)
    with pytest.raises(sqlite3.OperationalError):
        temp_db.create_user_with_password("Anna", HASH_A, SALT_A, ["Mejeri"])
    assert temp_db.get_users() == []  # no user without a password left behind


def test_create_user_with_password_rejects_taken_name(temp_db):
    temp_db.create_user_with_password("Anna", HASH_A, SALT_A)
    with pytest.raises(db.UserNameTaken):
        temp_db.create_user_with_password(" Anna ", HASH_B, SALT_B)
    assert temp_db.get_login("Anna").password_hash == HASH_A


@pytest.mark.parametrize("existing, new", [("Anna", "anna"), ("Anna", "ANNA"), ("Åsa", "åsa"), ("ÖRJAN", "örjan")])
def test_names_differing_only_in_case_are_taken(temp_db, existing, new):
    temp_db.create_user_with_password(existing, HASH_A, SALT_A)
    with pytest.raises(db.UserNameTaken) as error:
        temp_db.create_user_with_password(new, HASH_B, SALT_B)
    assert error.value.params == {"name": new}
    with pytest.raises(db.UserNameTaken):
        temp_db.create_user(new)
    assert [user.name for user in temp_db.get_users()] == [existing]


def test_get_login_for_unknown_user_or_user_without_password_is_none(temp_db):
    temp_db.create_user("NoPassword")
    assert temp_db.get_login("Nobody") is None
    assert temp_db.get_login("NoPassword") is None


@pytest.mark.parametrize("typed", ["Anna", "  Anna ", "anna", "ANNA", " aNNa "])
def test_get_login_ignores_surrounding_spaces_and_letter_case(temp_db, typed):
    anna = temp_db.create_user_with_password("Anna", HASH_A, SALT_A)
    login = temp_db.get_login(typed)
    assert login.user.id == anna
    assert login.user.name == "Anna"  # the name as registered


@pytest.mark.parametrize("registered, typed", [("Åsa", "åsa"), ("ÖRJAN", "örjan"), ("Straße", "STRASSE")])
def test_get_login_folds_letters_outside_a_to_z(temp_db, registered, typed):
    temp_db.create_user_with_password(registered, HASH_A, SALT_A)
    assert temp_db.get_login(typed).user.name == registered


def test_get_login_finds_only_that_user(temp_db):
    temp_db.create_user_with_password("Anna", HASH_A, SALT_A)
    temp_db.create_user_with_password("Bo", HASH_B, SALT_B)
    assert temp_db.get_login("bo").password_hash == HASH_B
    assert temp_db.get_login("annA").password_hash == HASH_A
    assert temp_db.get_login("Annika") is None


def test_get_user_by_name_ignores_letter_case_too(temp_db):
    anna = temp_db.create_user("Anna")
    assert temp_db.get_user_by_name("ANNA").id == anna


def test_set_password_adds_and_replaces_only_for_that_user(temp_db):
    anna = temp_db.create_user_with_password("Anna", HASH_A, SALT_A)
    bo = temp_db.create_user("Bo")

    assert temp_db.set_password(bo, HASH_B, SALT_B) is True
    assert temp_db.get_login("Bo").password_hash == HASH_B

    assert temp_db.set_password(anna, HASH_B, SALT_B) is True
    assert temp_db.get_login("Anna") == db.Login(db.User(anna, "Anna"), HASH_B, SALT_B)
    assert temp_db.get_login("Bo").salt == SALT_B


def test_set_password_for_unknown_user_returns_false(temp_db):
    assert temp_db.set_password(999, HASH_A, SALT_A) is False
    conn = sqlite3.connect(temp_db.DB_PATH)
    assert conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0] == 0


def test_credentials_are_removed_with_the_user(temp_db):
    anna = temp_db.create_user_with_password("Anna", HASH_A, SALT_A)
    with temp_db.transaction() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (anna,))
    conn = sqlite3.connect(temp_db.DB_PATH)
    assert conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0] == 0


def test_get_user_by_name(temp_db):
    anna = temp_db.create_user("Anna")
    assert temp_db.get_user_by_name(" Anna ") == db.User(anna, "Anna")
    assert temp_db.get_user_by_name("anna") == db.User(anna, "Anna")  # as at registration
    assert temp_db.get_user_by_name("Annika") is None
