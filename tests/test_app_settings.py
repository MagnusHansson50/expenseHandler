"""The Settings section in the sidebar: the highest price per item."""

import pandas as pd
import pytest

from test_app import create_user, log_out, start_app


@pytest.fixture
def anna(temp_db):
    at = start_app()
    create_user(at, "Anna")
    return at


def max_price_field(at):
    return at.sidebar.number_input(key="settings_max_price")


def save_settings(at, value):
    max_price_field(at).set_value(value)
    next(b for b in at.sidebar.button if b.label == "💾 Save settings").click().run()


def user_id(db, name):
    return next(user.id for user in db.get_users() if user.name == name)


def test_the_section_shows_the_default(anna):
    assert any(e.label == "⚙️ Settings" for e in anna.sidebar.expander)
    assert max_price_field(anna).value == 100_000
    assert (max_price_field(anna).proto.min, max_price_field(anna).proto.max) == (1_000, 10_000_000)


def test_saving_a_new_max_price(anna, temp_db):
    save_settings(anna, 250_000.0)
    assert not anna.exception
    assert temp_db.get_max_price(user_id(temp_db, "Anna")) == 250_000
    assert anna.success[0].value == "The highest price per item is now 250,000.00\xa0kr."
    assert max_price_field(anna).value == 250_000
    # The receipt form follows it at once.
    price = next(w for w in anna.number_input if w.label == "Price (kr)")
    assert price.proto.max == 250_000


def test_a_receipt_above_the_old_limit_can_be_saved_after_raising_it(anna, temp_db):
    anna.session_state["receipt_df"] = pd.DataFrame(
        [{"Item": "Car repair", "Price": 150_000.0, "Category": "Other"}]
    )
    anna.run()
    next(b for b in anna.button if b.label == "💾 Save").click().run()
    assert "Row 1: the price must be between -100,000 and 100,000 kr." in anna.error[0].value
    assert "under ⚙️ Settings" in anna.error[0].value
    save_settings(anna, 200_000.0)
    next(b for b in anna.button if b.label == "💾 Save").click().run()
    assert temp_db.get_history_dates(user_id(temp_db, "Anna"))


def test_the_setting_is_per_user(anna, temp_db):
    save_settings(anna, 250_000.0)
    log_out(anna)
    create_user(anna, "Bo")
    assert max_price_field(anna).value == 100_000
    assert temp_db.get_max_price(user_id(temp_db, "Bo")) == 100_000


def test_the_setting_is_kept_after_logging_in_again(anna):
    from test_app import log_in

    save_settings(anna, 5_000.0)
    log_out(anna)
    log_in(anna, "Anna")
    assert max_price_field(anna).value == 5_000


def test_the_section_in_swedish(temp_db):
    at = start_app(lang="sv")
    create_user(at, "Anna")
    assert any(e.label == "⚙️ Inställningar" for e in at.sidebar.expander)
    assert max_price_field(at).label == "Högsta belopp per vara (kr)"
    max_price_field(at).set_value(250_000.0)
    next(b for b in at.sidebar.button if b.label == "💾 Spara inställningar").click().run()
    assert at.success[0].value == "Högsta belopp per vara är nu 250\xa0000,00\xa0kr."
