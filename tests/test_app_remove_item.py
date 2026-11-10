"""Removing an item from the receipt being edited ("🗑️ Remove an item")."""

import pytest

from test_app import add_manual_purchase, create_user, start_app


@pytest.fixture
def anna_with_draft(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Milk", 15.9)
    add_manual_purchase(at, "Gift", 99.0)
    add_manual_purchase(at, "Milk", 15.9)
    return at


def remove_box(at):
    return next(box for box in at.selectbox if box.label == "Item to remove")


def test_rows_are_listed_with_their_number(anna_with_draft):
    box = remove_box(anna_with_draft)
    assert box.options == ["Row 1: Milk – 15.90\xa0kr", "Row 2: Gift – 99.00\xa0kr", "Row 3: Milk – 15.90\xa0kr"]


def test_removing_a_row_takes_only_that_row(anna_with_draft):
    at = anna_with_draft
    remove_box(at).set_value(1)
    at.button(key="remove_item").click().run()
    assert not at.exception
    assert at.session_state["receipt_df"]["Item"].tolist() == ["Milk", "Milk"]
    assert at.metric[0].value == "31.80\xa0kr"
    assert remove_box(at).options == ["Row 1: Milk – 15.90\xa0kr", "Row 2: Milk – 15.90\xa0kr"]


def test_one_of_two_rows_with_the_same_name(anna_with_draft):
    at = anna_with_draft
    remove_box(at).set_value(2)
    at.button(key="remove_item").click().run()
    assert at.session_state["receipt_df"]["Item"].tolist() == ["Milk", "Gift"]


def test_a_removed_item_is_never_saved_or_remembered(anna_with_draft, temp_db):
    at = anna_with_draft
    remove_box(at).set_value(1)
    at.button(key="remove_item").click().run()
    next(b for b in at.button if "Save" in b.label).click().run()
    anna = temp_db.get_users()[0].id
    saved = temp_db.get_all_history(anna)["Item"].tolist()
    assert saved == ["Milk", "Milk"]
    assert "Gift" not in temp_db.load_memory(anna)


def test_removing_the_last_row_empties_the_receipt(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Gift", 99.0)
    at.button(key="remove_item").click().run()
    assert at.session_state["receipt_df"].empty
    assert not any(box.label == "Item to remove" for box in at.selectbox)
