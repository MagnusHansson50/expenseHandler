"""Adding a category whose name looks like one the user already has ("dairy" next to "Dairy").

The user is asked first and has to choose: "Add anyway" or "Cancel".
"""

import pytest

from test_app import WJ, create_user, log_out, start_app, widget
from test_app_review import add_category_in_popup, category_tags, popup_item, start_with


@pytest.fixture
def anna(temp_db):
    at = start_app()
    create_user(at, "Anna")
    return at


def user_id(db, name):
    return next(user.id for user in db.get_users() if user.name == name)


def submit_category(at, name):
    widget(at.text_input, "New category").input(name)
    next(b for b in at.button if b.label == "➕ Add").click().run()


def question(at):
    return [w.value for w in at.main.warning if "anyway" in w.value]


def test_a_similar_name_is_asked_about_and_not_added_yet(anna, temp_db):
    submit_category(anna, "dairy")
    assert not anna.exception
    assert question(anna) == ["You already have the category 'Dairy'. Add 'dairy' anyway?"]
    assert "dairy" not in temp_db.get_categories(user_id(temp_db, "Anna"))


def test_add_anyway_adds_it(anna, temp_db):
    submit_category(anna, "DAIRY")
    anna.button(key="add_similar_category").click().run()
    assert not anna.exception
    assert anna.success[0].value == "Added category 'DAIRY'."
    categories = temp_db.get_categories(user_id(temp_db, "Anna"))
    assert "DAIRY" in categories and "Dairy" in categories
    assert not question(anna) and anna.session_state["pending_category"] is None


def test_cancel_adds_nothing(anna, temp_db):
    before = temp_db.get_categories(user_id(temp_db, "Anna"))
    submit_category(anna, "dairy")
    anna.button(key="cancel_similar_category").click().run()
    assert not anna.exception
    assert temp_db.get_categories(user_id(temp_db, "Anna")) == before
    assert not question(anna)
    assert not any(b.key == "add_similar_category" for b in anna.button)


def test_the_question_waits_for_an_answer(anna, temp_db):
    submit_category(anna, "dairy")
    anna.run()  # any other rerun, e.g. another widget
    assert question(anna)
    assert "dairy" not in temp_db.get_categories(user_id(temp_db, "Anna"))


def test_extra_spaces_inside_the_name_count_as_similar(anna):
    submit_category(anna, "Meat  &   fish")
    assert question(anna)
    assert anna.session_state["pending_category"] == ("Meat  &   fish", "Meat & Fish")


def test_the_same_name_is_refused_with_its_own_message(anna):
    submit_category(anna, "Dairy")
    assert anna.error[0].value == "Category 'Dairy' already exists."
    assert not question(anna)


def test_the_fallback_label_is_refused_without_a_question(anna):
    submit_category(anna, "other")
    assert not question(anna)
    assert anna.error[0].value.startswith("Enter a name of 1–50 characters")


def test_a_different_name_is_added_at_once(anna):
    submit_category(anna, "Dairy products")
    assert anna.success[0].value == "Added category 'Dairy products'."
    assert not question(anna)


def test_a_new_name_replaces_the_question(anna):
    submit_category(anna, "dairy")
    submit_category(anna, "Candy")
    assert not question(anna)
    assert anna.success[0].value == "Added category 'Candy'."


def test_logging_out_forgets_the_question(anna):
    submit_category(anna, "dairy")
    log_out(anna)
    assert anna.session_state["pending_category"] is None
    create_user(anna, "Bo")
    assert not question(anna)


def test_only_the_users_own_categories_count(anna, temp_db):
    submit_category(anna, "Candy")
    log_out(anna)
    create_user(anna, "Bo")
    submit_category(anna, "candy")  # Anna's "Candy" is not Bo's
    assert not question(anna)
    assert "candy" in temp_db.get_categories(user_id(temp_db, "Bo"))


def test_names_in_the_question_are_shown_literally(anna):
    submit_category(anna, "**Bold** [x](https://evil.test)")
    submit_category(anna, "**bold** [x](https://evil.test)")
    assert question(anna) == [
        rf"You already have the category '\*\*Bold\*\* \[x\]\(https\:{WJ}\/\/evil\.test\)'. "
        rf"Add '\*\*bold\*\* \[x\]\(https\:{WJ}\/\/evil\.test\)' anyway?"
    ]


def test_the_question_in_swedish(temp_db):
    at = start_app(lang="sv")
    create_user_sv(at, "Anna")
    widget(at.text_input, "Ny kategori").input("mejeri")
    next(b for b in at.button if b.label == "➕ Lägg till").click().run()
    assert [w.value for w in at.main.warning if "ändå" in w.value] == [
        "Du har redan kategorin 'Mejeri'. Vill du ändå lägga till 'mejeri'?"
    ]
    assert at.button(key="add_similar_category").label == "Lägg till ändå"
    assert at.button(key="cancel_similar_category").label == "Avbryt"
    widget(at.text_input, "Ny kategori").input("Mejeri")
    next(b for b in at.button if b.label == "➕ Lägg till").click().run()
    assert at.error[0].value == "Kategorin 'Mejeri' finns redan."


def create_user_sv(at, name):
    create_user(at, name)  # the form is found by keys, so it works in any language


# --- In the review popup -----------------------------------------------------
# The same question inside the popup for items without a category. Its buttons
# are handled at the top of the popup's next run, so it stays on the same item.


def popup_question(at):
    return [w.value for w in at.warning if "anyway" in w.value]


@pytest.fixture
def popup(anna):
    start_with(anna, ("Drill", 799.0), ("Gloves", 99.0))
    return anna


def test_the_popup_asks_about_a_similar_name(popup, temp_db):
    add_category_in_popup(popup, "dairy")
    assert not popup.exception
    assert popup_question(popup) == ["You already have the category 'Dairy'. Add 'dairy' anyway?"]
    assert "dairy" not in temp_db.get_categories(user_id(temp_db, "Anna"))
    assert "dairy" not in category_tags(popup).options
    assert popup_item(popup)[1] == "**Drill**"


def test_add_anyway_in_the_popup_adds_a_tag_and_stays_on_the_item(popup, temp_db):
    add_category_in_popup(popup, "dairy")
    popup.button(key="review_add_similar").click().run()
    assert not popup.exception
    assert "dairy" in temp_db.get_categories(user_id(temp_db, "Anna"))
    assert "dairy" in category_tags(popup).options
    assert popup.success[0].value == "Added category 'dairy'."
    assert not popup_question(popup)
    assert popup_item(popup)[1] == "**Drill**"


def test_cancel_in_the_popup_adds_nothing_and_stays_on_the_item(popup, temp_db):
    before = temp_db.get_categories(user_id(temp_db, "Anna"))
    add_category_in_popup(popup, "dairy")
    popup.button(key="review_cancel_similar").click().run()
    assert not popup.exception
    assert temp_db.get_categories(user_id(temp_db, "Anna")) == before
    assert not popup_question(popup)
    assert not any(b.key == "review_add_similar" for b in popup.button)
    assert popup_item(popup)[1] == "**Drill**"


def test_the_popup_question_does_not_show_behind_it_on_the_page(popup):
    add_category_in_popup(popup, "dairy")
    assert popup.session_state["pending_category"] is None  # "Manage categories" asks nothing


def test_stopping_the_review_drops_the_question(popup):
    add_category_in_popup(popup, "dairy")
    popup.button(key="review_stop").click().run()
    assert popup_item(popup) is None
    assert popup.session_state["review_pending_category"] is None
    popup.button(key="review_open").click().run()
    assert not popup_question(popup)


def test_names_in_the_popup_question_are_shown_literally(popup):
    add_category_in_popup(popup, "**Bold**")
    add_category_in_popup(popup, "**bold**")
    assert popup_question(popup) == [r"You already have the category '\*\*Bold\*\*'. Add '\*\*bold\*\*' anyway?"]
