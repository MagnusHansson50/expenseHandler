"""Showing only some categories in the History tab.

The filter is a multiselect above the totals; the total, the number of
purchases, the chart and the list follow it, while deleting a date and the
backup do not. The filtering itself is tested in test_history.py.
"""

from datetime import date, timedelta

import pandas as pd
import pytest
from streamlit.dataframe_util import convert_arrow_bytes_to_pandas_df

from test_app import create_user, log_out, start_app
from test_app_history_edit import history_editor


def save(db, user_id, *rows, day=None):
    db.save_receipt(
        user_id, day or date.today(),
        pd.DataFrame(list(rows), columns=["Item", "Price", "Category"]),
        {},
    )


@pytest.fixture
def anna(temp_db):
    at = start_app()
    create_user(at, "Anna")
    anna_id = temp_db.get_users()[0].id
    save(temp_db, anna_id, ("Milk", 15.9, "Dairy"), ("Cola", 20.0, "Drinks"), ("Chips", 25.0, "Other"))
    return at.run()


def history_filter(at):
    return at.multiselect(key="history_filter")


def choose(at, *categories):
    history_filter(at).set_value(list(categories)).run()


def metrics(at):
    return [metric.value for metric in at.metric]


def listed_items(at):
    return convert_arrow_bytes_to_pandas_df(history_editor(at).proto.arrow_data.data)["Item"].tolist()


def chart_categories(at):
    """The categories the history bar chart has bars for."""
    def walk(node):
        yield node
        for child in getattr(node, "children", {}).values():
            yield from walk(child)

    chart = next(node for node in walk(at._tree) if getattr(node, "type", "") == "vega_lite_chart").proto
    frames = [convert_arrow_bytes_to_pandas_df(d.data.data) for d in chart.datasets]
    if chart.HasField("data"):
        frames.append(convert_arrow_bytes_to_pandas_df(chart.data.data))
    data = next(frame for frame in frames if "Category" in frame.columns)
    return sorted(data["Category"].tolist())


def test_everything_is_shown_until_a_category_is_chosen(anna):
    assert history_filter(anna).value == []
    assert history_filter(anna).placeholder == "All categories"
    assert metrics(anna) == ["60.90\xa0kr", "3"]
    assert sorted(listed_items(anna)) == ["Chips", "Cola", "Milk"]
    assert not any("Showing" in c.value for c in anna.caption)


def test_the_users_categories_can_be_chosen_with_labels(anna, temp_db):
    widget = history_filter(anna)
    assert widget.options == [  # labels, in the user's order
        "Other" if name == "Other" else name for name in temp_db.get_categories(temp_db.get_users()[0].id)
    ]


def test_choosing_one_category_filters_total_count_chart_and_list(anna):
    choose(anna, "Drinks")
    assert not anna.exception
    assert metrics(anna) == ["20.00\xa0kr", "1"]
    assert listed_items(anna) == ["Cola"]
    assert chart_categories(anna) == ["Drinks"]
    assert any(c.value.startswith("Showing 1 of ") for c in anna.caption)


def test_several_categories_can_be_chosen(anna):
    choose(anna, "Drinks", "Other")
    assert metrics(anna) == ["45.00\xa0kr", "2"]
    assert sorted(listed_items(anna)) == ["Chips", "Cola"]


def test_a_category_without_purchases_says_so(anna):
    choose(anna, "Pantry")
    assert "No purchases in the chosen categories in this period." in [i.value for i in anna.info]
    assert not anna.metric


def test_clearing_the_filter_shows_everything_again(anna):
    choose(anna, "Drinks")
    choose(anna)
    assert metrics(anna) == ["60.90\xa0kr", "3"]


def test_the_choice_stays_when_the_period_changes(anna, temp_db):
    save(temp_db, temp_db.get_users()[0].id, ("Juice", 30.0, "Drinks"), day=date.today() - timedelta(days=40))
    choose(anna, "Drinks")
    next(d for d in anna.date_input if d.label == "Start date").set_value(date.today() - timedelta(days=60)).run()
    assert history_filter(anna).value == ["Drinks"]
    assert metrics(anna) == ["50.00\xa0kr", "2"]


def test_the_choice_stays_when_the_language_changes(anna):
    choose(anna, "Other")
    anna.sidebar.selectbox(key="language").set_value("sv").run()
    assert history_filter(anna).value == ["Other"]  # stored name; shown as "Övrigt"
    assert "Övrigt" in history_filter(anna).options
    assert history_filter(anna).placeholder == "Alla kategorier"
    assert metrics(anna) == ["25,00\xa0kr", "1"]
    assert any(c.value == "Visar 1 av 11 kategorier." for c in anna.caption)


def test_a_removed_category_still_in_the_history_can_be_chosen(anna, temp_db):
    anna_id = temp_db.get_users()[0].id
    temp_db.add_category(anna_id, "Candy")
    save(temp_db, anna_id, ("Gum", 10.0, "Candy"))
    temp_db.delete_category(anna_id, "Candy")
    anna.run()
    assert "Candy" in history_filter(anna).options
    choose(anna, "Candy")
    assert listed_items(anna) == ["Gum"]


def test_logging_out_forgets_the_choice_and_other_users_see_only_their_own(anna, temp_db):
    temp_db.add_category(temp_db.get_users()[0].id, "Tools")
    choose(anna, "Drinks")
    log_out(anna)
    assert anna.session_state["history_categories"] == []
    create_user(anna, "Bo")
    assert history_filter(anna).value == []
    assert "Tools" not in history_filter(anna).options


def test_deleting_a_date_says_it_ignores_the_filter(anna):
    assert any(
        c.value == "Every purchase saved on that date is deleted, also in categories the filter hides."
        for c in anna.caption
    )
