"""Going through items without a category in a popup (st.dialog).

AppTest renders the popup's contents while it is open; closing it with the
window's X (on_dismiss) cannot be clicked here and is checked in a browser.
"""

from core.constants import FALLBACK_CATEGORY
from test_app import add_manual_purchase, create_user, log_out, start_app, widget


def open_button(at):
    """The label of the button that opens the popup, or None if it is not shown."""
    buttons = [button.label for button in at.button if button.key == "review_open"]
    return buttons[0] if buttons else None


def popup_item(at):
    """(position text, item name, amount) in the open popup, or None if it is closed."""
    tags = [group for group in at.get("button_group") if group.key and group.key.startswith("review_category_")]
    if not tags:
        return None
    position = at.get("progress")[0].proto.text
    texts = [md.value for md in at.markdown]
    name = next(text for text in texts if text.startswith("**"))
    amount = texts[texts.index(name) + 1]
    return position, name, amount


def category_tags(at):
    return next(group for group in at.get("button_group") if group.key.startswith("review_category_"))


def choose(at, label):
    category_tags(at).set_value(label).run()


def draft_categories(at):
    return dict(zip(at.session_state["receipt_df"]["Item"], at.session_state["receipt_df"]["Category"]))


def add_categorized_purchase(at, item, price, category):
    widget(at.text_input, "Item").input(item)
    widget(at.number_input, "Price (kr)").set_value(price)
    widget(at.selectbox, "Category").set_value(category)
    next(b for b in at.button if "Add to list" in b.label).click().run()


def start_with(at, *items):
    for item, price in items:
        add_manual_purchase(at, item, price)
    at.button(key="review_open").click().run()


def save_receipt(at):
    next(b for b in at.button if "Save" in b.label and b.key is None).click().run()


# --- The button above the table ----------------------------------------------


def test_no_button_without_a_receipt(temp_db):
    at = start_app()
    create_user(at, "Anna")
    assert open_button(at) is None


def test_the_button_counts_items_without_a_category(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Drill", 799.0)  # the form defaults to the fallback category
    add_manual_purchase(at, "Gloves", 99.0)
    assert open_button(at) == "🏷️ Go through items without a category (2)"
    assert popup_item(at) is None  # adding by hand does not open the popup


def test_no_button_when_every_item_has_a_category(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_categorized_purchase(at, "Milk", 15.9, "Dairy")
    assert open_button(at) is None


def test_items_filed_as_other_on_purpose_are_not_counted(temp_db):
    at = start_app()
    create_user(at, "Anna")
    temp_db.save_memory(temp_db.get_user_by_name("Anna").id, {"Gift card": FALLBACK_CATEGORY})
    add_manual_purchase(at, "Gift card", 200.0)
    assert open_button(at) is None


# --- The popup ---------------------------------------------------------------


def test_the_popup_shows_one_item_at_a_time_and_a_click_chooses(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0))
    assert popup_item(at) == ("Item 1 of 2", "**Drill**", "799.00 kr")
    assert "Dairy" in category_tags(at).options and "Other" in category_tags(at).options
    assert open_button(at) is None  # hidden while the popup is open

    choose(at, "Dairy")
    assert draft_categories(at)["Drill"] == "Dairy"
    assert popup_item(at) == ("Item 2 of 2", "**Gloves**", "99.00 kr")
    assert category_tags(at).value is None  # no choice carried over

    choose(at, "Other")
    assert popup_item(at) is None
    assert at.success[0].value.startswith("Every item now has a category.")
    assert at.session_state["review_active"] is False
    assert open_button(at) is None


def test_skipped_items_are_counted_and_the_button_stays(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0))
    at.button(key="review_skip").click().run()
    choose(at, "Dairy")
    assert popup_item(at) is None
    assert at.info[0].value == "The review is done. Items you skipped that still have no category: 1."
    assert draft_categories(at) == {"Drill": FALLBACK_CATEGORY, "Gloves": "Dairy"}
    assert open_button(at) == "🏷️ Go through items without a category (1)"


def test_stop_closes_the_popup_and_keeps_what_was_chosen(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0), ("Saw", 199.0))
    choose(at, "Dairy")
    at.button(key="review_stop").click().run()
    assert popup_item(at) is None
    assert draft_categories(at) == {"Drill": "Dairy", "Gloves": FALLBACK_CATEGORY, "Saw": FALLBACK_CATEGORY}
    assert at.session_state["review_dismissed"] == ["Gloves", "Saw"]
    assert open_button(at) == "🏷️ Go through items without a category (2)"  # can be opened again


def test_reopening_starts_with_the_items_left(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gloves", 99.0))
    choose(at, "Dairy")
    at.button(key="review_stop").click().run()
    at.button(key="review_open").click().run()
    assert popup_item(at) == ("Item 1 of 1", "**Gloves**", "99.00 kr")


def test_item_names_are_shown_literally(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("![x](http://example.com/a.png)", 1.0))
    assert r"\!\[x\]" in popup_item(at)[1]


# --- What is remembered --------------------------------------------------------


def test_choices_are_remembered_for_the_next_receipt(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0))
    choose(at, "Dairy")
    save_receipt(at)
    anna = temp_db.get_user_by_name("Anna").id
    assert temp_db.load_memory(anna) == {"Drill": "Dairy"}


def test_skipped_items_are_asked_about_again_and_other_on_purpose_is_remembered(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0), ("Gift card", 200.0))
    at.button(key="review_skip").click().run()
    choose(at, "Other")  # on purpose
    save_receipt(at)

    anna = temp_db.get_user_by_name("Anna").id
    assert temp_db.load_memory(anna) == {"Gift card": FALLBACK_CATEGORY}
    add_manual_purchase(at, "Drill", 799.0)
    add_manual_purchase(at, "Gift card", 200.0)
    assert open_button(at) == "🏷️ Go through items without a category (1)"


def test_a_new_receipt_or_logging_out_resets_the_review(temp_db):
    at = start_app()
    create_user(at, "Anna")
    start_with(at, ("Drill", 799.0))
    log_out(at)
    assert at.session_state["review_active"] is False
    assert at.session_state["review_dismissed"] == []
