"""Password hashing and rules (core/auth.py). Only test passwords are used here."""

import pytest

from core.auth import hash_password, password_problem, verify_password
from core.constants import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from core.receipt import Problem


def test_correct_password_verifies():
    password_hash, salt = hash_password("correct horse")
    assert verify_password("correct horse", password_hash, salt)


@pytest.mark.parametrize("attempt", ["correct hors", "Correct horse", "correct horse ", "", "x" * 20])
def test_wrong_password_does_not_verify(attempt):
    password_hash, salt = hash_password("correct horse")
    assert not verify_password(attempt, password_hash, salt)


def test_same_password_gets_different_salt_and_hash():
    first_hash, first_salt = hash_password("same password")
    second_hash, second_salt = hash_password("same password")
    assert first_salt != second_salt
    assert first_hash != second_hash
    assert len(first_salt) == 16 and len(first_hash) == 64


def test_hash_does_not_contain_the_password():
    password_hash, salt = hash_password("plain-text-secret")
    assert b"plain-text-secret" not in password_hash + salt


def test_unicode_forms_of_the_same_password_match():
    composed = "lösenord1"  # ö as one character
    decomposed = "lösenord1"  # o + combining diaeresis
    password_hash, salt = hash_password(composed)
    assert verify_password(decomposed, password_hash, salt)


def test_overlong_password_is_rejected_without_hashing(monkeypatch):
    password_hash, salt = hash_password("short enough")
    monkeypatch.setattr("core.auth._scrypt", lambda *_: pytest.fail("must not hash"))
    assert not verify_password("x" * (MAX_PASSWORD_LENGTH + 1), password_hash, salt)


@pytest.mark.parametrize(
    "password, problem",
    [
        ("x" * (MIN_PASSWORD_LENGTH - 1), Problem("password_too_short", {"min": MIN_PASSWORD_LENGTH})),
        ("x" * MIN_PASSWORD_LENGTH, None),
        ("x" * MAX_PASSWORD_LENGTH, None),
        ("x" * (MAX_PASSWORD_LENGTH + 1), Problem("password_too_long", {"max": MAX_PASSWORD_LENGTH})),
    ],
)
def test_password_length_rules(password, problem):
    assert password_problem(password) == problem
