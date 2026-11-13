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
    assert at.main.warning[0].value.startswith(
        "The list is 32.50\xa0kr less than the receipt's Betalat (paid) 48.40\xa0kr."
    )
    add_manual_purchase(at, "Bread", 32.5)
    assert not at.main.warning
    assert any(c.value == "✔️ The list matches the receipt's Betalat (paid) 48.40\xa0kr." for c in at.caption)


def test_too_much_is_shown_until_the_item_is_removed(anna):
    at = with_paid_total(anna, 15.9)
    add_manual_purchase(at, "Gift", 99.0)  # added by hand after the upload: not on the receipt
    assert at.main.warning[0].value.startswith(
        "The list is 99.00\xa0kr more than the receipt's Betalat (paid) 15.90\xa0kr."
    )
    next(box for box in at.selectbox if box.label == "Item to remove").set_value(1)
    at.button(key="remove_item").click().run()
    assert not at.main.warning


def test_an_item_removed_from_the_receipt_is_not_missing(anna):
    # Something bought for someone else: removed on purpose, so the list still matches.
    at = with_paid_total(anna, 15.9)
    add_manual_purchase(at, "Gift", 99.0)
    # As if both came from the receipt: its paid amount and its rows, as an upload sets them.
    at.session_state["paid_total"] = 114.9
    at.session_state["imported_rows"] = [["Milk", 15.9], ["Gift", 99.0]]
    at.run()
    assert any(c.value == "✔️ The list matches the receipt's Betalat (paid) 114.90\xa0kr." for c in at.caption)
    next(box for box in at.selectbox if box.label == "Item to remove").set_value(1)
    at.button(key="remove_item").click().run()
    assert not at.main.warning
    assert any(
        c.value == "✔️ The list matches the receipt's Betalat (paid) 114.90\xa0kr minus what you removed (99.00\xa0kr)."
        for c in at.caption
    )


def test_no_comparison_without_an_uploaded_receipt(anna):
    add_manual_purchase(anna, "Milk", 15.9)
    assert not anna.main.warning
    assert not any("Betalat" in c.value for c in anna.caption)


def test_clearing_the_list_forgets_the_amount_paid(anna):
    at = with_paid_total(anna, 48.4)
    next(box for box in at.selectbox if box.label == "Item to remove").set_value(0)
    at.button(key="remove_item").click().run()  # the only row: the list is empty again
    assert at.session_state["paid_total"] is None
    assert at.session_state["removed_total"] == 0.0


def test_clearing_the_list_with_the_button_forgets_it_too(anna):
    at = with_paid_total(anna, 48.4)
    next(b for b in at.button if "Clear list" in b.label).click().run()
    assert at.session_state["paid_total"] is None


def test_an_item_for_0_kr_is_not_added(anna):
    add_manual_purchase(anna, "Milk", 0.0)
    assert anna.session_state["receipt_df"].empty
    assert anna.error[0].value.startswith("Enter a price. An item for 0 kr is not added")


def test_a_negative_amount_is_still_added_as_a_discount(anna):
    add_manual_purchase(anna, "Discount", -10.0)
    assert anna.session_state["receipt_df"][["Item", "Price"]].values.tolist() == [["Discount", -10.0]]
