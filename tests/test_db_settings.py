"""A user's own settings in the database: the highest price per item."""

import sqlite3
from contextlib import closing

import pytest

from core.constants import MAX_PRICE, MAX_PRICE_CEILING, MAX_PRICE_SETTING_MIN


def test_without_a_choice_the_default_applies(temp_db):
    anna = temp_db.create_user("Anna")
    assert temp_db.get_max_price(anna) == MAX_PRICE


def test_a_chosen_max_price_is_kept_and_can_be_changed(temp_db):
    anna = temp_db.create_user("Anna")
    assert temp_db.set_max_price(anna, 250_000) is True
    assert temp_db.get_max_price(anna) == 250_000
    temp_db.set_max_price(anna, 5_000)
    assert temp_db.get_max_price(anna) == 5_000


def test_the_setting_is_per_user(temp_db):
    anna, bo = temp_db.create_user("Anna"), temp_db.create_user("Bo")
    temp_db.set_max_price(anna, 250_000)
    assert temp_db.get_max_price(bo) == MAX_PRICE


@pytest.mark.parametrize("value", [MAX_PRICE_SETTING_MIN - 1, MAX_PRICE_CEILING + 1, 0, -5_000])
def test_values_outside_the_range_are_refused_and_change_nothing(temp_db, value):
    anna = temp_db.create_user("Anna")
    temp_db.set_max_price(anna, 20_000)
    with pytest.raises(ValueError):
        temp_db.set_max_price(anna, value)
    assert temp_db.get_max_price(anna) == 20_000


@pytest.mark.parametrize("value", [MAX_PRICE_SETTING_MIN, MAX_PRICE_CEILING])
def test_the_ends_of_the_range_are_allowed(temp_db, value):
    anna = temp_db.create_user("Anna")
    temp_db.set_max_price(anna, value)
    assert temp_db.get_max_price(anna) == value


def test_an_unknown_user_gets_no_setting(temp_db):
    assert temp_db.set_max_price(999_999, 20_000) is False
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0


def test_the_setting_goes_with_the_user(temp_db):
    anna = temp_db.create_user("Anna")
    temp_db.set_max_price(anna, 250_000)
    temp_db.delete_user(anna)
    with closing(sqlite3.connect(temp_db.DB_PATH)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
