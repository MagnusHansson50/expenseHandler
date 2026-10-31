"""scripts/reset_password.py. Only test passwords are used here."""

import pytest

from scripts import reset_password
from services import auth

OLD = "old-test-password"
NEW = "new-test-password"


def run(argv, answers):
    """Run the script with scripted password answers; return (exit code, output lines, prompts)."""
    output, prompts = [], []
    replies = iter(answers)

    def ask(prompt):
        prompts.append(prompt)
        return next(replies)

    code = reset_password.main(argv, ask_password=ask, out=output.append)
    return code, output, prompts


@pytest.fixture
def anna(temp_db):
    return auth.register("Anna", OLD, [])


def test_reset_changes_the_password(anna):
    code, output, prompts = run(["Anna"], [NEW, NEW])
    assert code == reset_password.EXIT_OK
    assert output == ["The password for 'Anna' has been changed."]
    assert len(prompts) == 2
    assert auth.authenticate("Anna", NEW) == anna
    assert auth.authenticate("Anna", OLD) is None


def test_password_is_never_printed(anna):
    _, output, prompts = run(["Anna"], [NEW, NEW])
    assert NEW not in "\n".join(output + prompts)


def test_mismatched_passwords_change_nothing(anna):
    code, output, _ = run(["Anna"], [NEW, "something-else"])
    assert code == reset_password.EXIT_BAD_INPUT
    assert "do not match" in output[0]
    assert auth.authenticate("Anna", OLD) == anna


def test_too_short_password_changes_nothing(anna):
    code, output, _ = run(["Anna"], ["short", "short"])
    assert code == reset_password.EXIT_BAD_INPUT
    assert "password_too_short" in output[0]
    assert auth.authenticate("Anna", OLD) == anna


def test_unknown_user_is_reported_before_asking_for_a_password(temp_db):
    code, output, prompts = run(["Nobody"], [])
    assert code == reset_password.EXIT_UNKNOWN_USER
    assert output[0].startswith("No user named 'Nobody'")
    assert prompts == []


@pytest.mark.parametrize("argv", [[], ["  "], ["Anna", "extra"]])
def test_wrong_arguments_print_usage(temp_db, argv):
    code, output, _ = run(argv, [])
    assert code == reset_password.EXIT_BAD_INPUT
    assert output[0].startswith("Usage:")


def test_user_without_password_can_be_given_one(temp_db):
    temp_db.create_user("Old")
    code, _, _ = run(["Old"], [NEW, NEW])
    assert code == reset_password.EXIT_OK
    assert auth.authenticate("Old", NEW).name == "Old"
