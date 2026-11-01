"""The question about items without a category, above the receipt table."""

from core.constants import FALLBACK_CATEGORY
from test_app import add_manual_purchase, create_user, log_out, start_app, widget


def prompt(at):
    """The review question, or None if it is not shown."""
    texts = [md.value for md in at.markdown if "without a category" in md.value]
    return texts[0] if texts else None


def has_button(at, key):
    return any(button.key == key for button in at.button)


def add_categorized_purchase(at, item, price, category):
    widget(at.text_input, "Item").input(item)
    widget(at.number_input, "Price (kr)").set_value(price)
    widget(at.selectbox, "Category").set_value(category)
    next(b for b in at.button if "Add to list" in b.label).click().run()


def test_no_question_without_a_receipt(temp_db):
    at = start_app()
    create_user(at, "Anna")
    assert prompt(at) is None


def test_question_counts_items_without_a_category(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Drill", 799.0)  # the form defaults to the fallback category
    add_manual_purchase(at, "Gloves", 99.0)
    assert prompt(at) == "Items without a category: 2. Do you want to go through them now?"
    assert has_button(at, "review_start") and has_button(at, "review_dismiss")


def test_no_question_when_every_item_has_a_category(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_categorized_purchase(at, "Milk", 15.9, "Dairy")
    assert prompt(at) is None


def test_items_filed_as_other_on_purpose_are_not_asked_about(temp_db):
    at = start_app()
    create_user(at, "Anna")
    temp_db.save_memory(temp_db.get_user_by_name("Anna").id, {"Gift card": FALLBACK_CATEGORY})
    add_manual_purchase(at, "Gift card", 200.0)
    assert prompt(at) is None


def test_not_now_hides_the_question_until_new_items_need_a_category(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Drill", 799.0)
    at.button(key="review_dismiss").click().run()
    assert prompt(at) is None

    add_categorized_purchase(at, "Milk", 15.9, "Dairy")
    assert prompt(at) is None  # nothing new to ask about

    add_manual_purchase(at, "Gloves", 99.0)
    assert prompt(at) == "Items without a category: 2. Do you want to go through them now?"


def test_go_through_starts_the_review_and_hides_the_question(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Drill", 799.0)
    at.button(key="review_start").click().run()
    assert at.session_state["review_active"] is True
    assert prompt(at) is None


def test_a_new_receipt_asks_again(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Drill", 799.0)
    at.button(key="review_dismiss").click().run()
    next(b for b in at.button if "Clear" in b.label).click().run()
    add_manual_purchase(at, "Drill", 799.0)
    assert prompt(at) == "Items without a category: 1. Do you want to go through them now?"


def test_logging_out_forgets_the_review_state(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Drill", 799.0)
    at.button(key="review_start").click().run()
    log_out(at)
    assert at.session_state["review_active"] is False
    assert at.session_state["review_dismissed"] == []
