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


# --- The review, one item at a time --------------------------------------


def review_text(at):
    texts = [md.value for md in at.markdown if md.value.startswith("Item ")]
    return texts[0] if texts else None


def category_choice(at):
    return next(box for box in at.selectbox if box.key and box.key.startswith("review_category_"))


def draft_categories(at):
    return dict(zip(at.session_state["receipt_df"]["Item"], at.session_state["receipt_df"]["Category"]))


def start_with(at, *items):
    for item, price in items:
        add_manual_purchase(at, item, price)
    at.button(key="review_start").click().run()


def test_review_shows_one_item_at_a_time_and_sets_its_category(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0))
    assert review_text(at) == "Item 1 of 2: **Drill** (799.00 kr)"

    category_choice(at).set_value("Dairy")
    at.button(key="review_save").click().run()
    assert draft_categories(at)["Drill"] == "Dairy"
    assert review_text(at) == "Item 2 of 2: **Gloves** (99.00 kr)"
    assert category_choice(at).value is None  # no choice carried over

    category_choice(at).set_value("Other")
    at.button(key="review_save").click().run()
    assert review_text(at) is None
    assert at.success[0].value.startswith("Every item now has a category.")
    assert at.session_state["review_active"] is False
    assert prompt(at) is None


def test_saving_without_a_choice_asks_for_one(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0))
    at.button(key="review_save").click().run()
    assert at.error[0].value == "Choose a category first, or skip the item."
    assert review_text(at) == "Item 1 of 1: **Drill** (799.00 kr)"
    assert draft_categories(at)["Drill"] == FALLBACK_CATEGORY


def test_skipped_items_are_counted_and_not_asked_about_again(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0))
    at.button(key="review_skip").click().run()
    category_choice(at).set_value("Dairy")
    at.button(key="review_save").click().run()
    assert at.info[0].value == "The review is done. Items you skipped that still have no category: 1."
    assert draft_categories(at) == {"Drill": FALLBACK_CATEGORY, "Gloves": "Dairy"}
    assert prompt(at) is None


def test_stop_ends_the_review_and_keeps_what_was_chosen(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0), ("Saw", 199.0))
    category_choice(at).set_value("Dairy")
    at.button(key="review_save").click().run()
    at.button(key="review_stop").click().run()
    assert review_text(at) is None
    assert prompt(at) is None
    assert draft_categories(at) == {"Drill": "Dairy", "Gloves": FALLBACK_CATEGORY, "Saw": FALLBACK_CATEGORY}


def test_choices_are_remembered_for_the_next_receipt(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0))
    category_choice(at).set_value("Dairy")
    at.button(key="review_save").click().run()
    next(b for b in at.button if "Save" in b.label and b.key != "review_save").click().run()
    anna = temp_db.get_user_by_name("Anna").id
    assert temp_db.load_memory(anna) == {"Drill": "Dairy"}


def test_item_names_are_shown_literally(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("![x](http://example.com/a.png)", 1.0))
    assert r"\!\[x\]" in review_text(at)


def test_skipped_items_are_asked_about_again_on_the_next_receipt(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gift card", 200.0))
    at.button(key="review_skip").click().run()
    category_choice(at).set_value("Other")  # on purpose
    at.button(key="review_save").click().run()
    next(b for b in at.button if "Save" in b.label and b.key != "review_save").click().run()

    anna = temp_db.get_user_by_name("Anna").id
    assert temp_db.load_memory(anna) == {"Gift card": FALLBACK_CATEGORY}
    add_manual_purchase(at, "Drill", 799.0)
    add_manual_purchase(at, "Gift card", 200.0)
    assert prompt(at) == "Items without a category: 1. Do you want to go through them now?"
