"""Adding a missing item, and comparing the list with the amount paid while editing.

AppTest cannot upload a PDF, so the amount paid an upload would set is put in
session state directly (st.session_state.paid_total); the upload itself is
checked in a browser. Warnings are looked for in the main area (the sidebar always has one).
"""

import pytest

from test_app import add_manual_purchase, create_user, start_app


@pytest.fixture
def anna(temp_db):
    at = start_app()
    create_user(at, "Anna")
    return at


def expander_labels(at):
    return [expander.label for expander in at.expander]


def test_the_form_is_above_the_upload_while_the_list_is_empty(anna):
    assert "✍️ Add a purchase manually" in expander_labels(anna)
    assert "➕ Add a missing item" not in expander_labels(anna)


def test_the_form_moves_below_the_table_once_there_is_a_list(anna):
    add_manual_purchase(anna, "Milk", 15.9)
    labels = expander_labels(anna)
    assert "➕ Add a missing item" in labels and "✍️ Add a purchase manually" not in labels
    assert labels.index("➕ Add a missing item") < labels.index("🗑️ Remove an item")
    add_manual_purchase(anna, "Bread", 32.5)  # the moved form still adds to the list
    assert anna.session_state["receipt_df"]["Item"].tolist() == ["Milk", "Bread"]


def with_paid_total(at, paid):
    add_manual_purchase(at, "Milk", 15.9)
    at.session_state["paid_total"] = paid
    return at.run()


def test_missing_amount_is_shown_until_the_item_is_added(anna):
    at = with_paid_total(anna, 48.4)
    assert at.main.warning[0].value.startswith("The receipt says Betalat (paid) 48.40\xa0kr, but the list is 32.50\xa0kr less.")
    add_manual_purchase(at, "Bread", 32.5)
    assert not at.main.warning
    assert any(c.value == "✔️ The list matches the receipt's Betalat (paid) 48.40\xa0kr." for c in at.caption)


def test_too_much_is_shown_until_the_item_is_removed(anna):
    at = with_paid_total(anna, 15.9)
    add_manual_purchase(at, "Gift", 99.0)
    assert at.main.warning[0].value.startswith("The receipt says Betalat (paid) 15.90\xa0kr, but the list is 99.00\xa0kr more.")
    next(box for box in at.selectbox if box.label == "Item to remove").set_value(1)
    at.button(key="remove_item").click().run()
    assert not at.main.warning


def test_no_comparison_without_an_uploaded_receipt(anna):
    add_manual_purchase(anna, "Milk", 15.9)
    assert not anna.main.warning
    assert not any("Betalat" in c.value for c in anna.caption)


def test_clearing_the_list_forgets_the_amount_paid(anna):
    at = with_paid_total(anna, 48.4)
    next(b for b in at.button if "Clear list" in b.label).click().run()
    assert at.session_state["paid_total"] is None
