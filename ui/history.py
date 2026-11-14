"""Tab "History": period and category filter, totals, the chart, the list where categories can
be changed, and deleting a date.
"""

from datetime import date

import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from core.calculator import sum_by_category, total_cost
from core.history import filter_by_categories, filter_categories
from core.i18n import category_label, format_amount, format_number, t
from integrations import db
from services import history as history_service
from ui.backup import render_backup
from ui.common import PRICE_INPUT_FORMAT, flash, lang, load, take_removal, write_errors


def render_delete_date(user_id):
    """Expander for removing everything saved on one date."""
    saved_dates = load(db.get_history_dates, user_id, what="what_saved_dates")
    if not saved_dates:
        return

    with st.expander(t("delete_receipt_expander", lang())):
        st.caption(t("delete_date_all_categories", lang()))
        with st.form("delete_date_form"):
            st.selectbox(t("col_date", lang()), options=saved_dates, key="delete_date_choice")
            st.checkbox(t("confirm_delete", lang()), key="delete_date_confirm")
            delete_clicked = st.form_submit_button(
                t("delete_button", lang()), on_click=take_removal, args=("delete_date_confirm", "delete_date_choice")
            )
        confirmed = st.session_state.pop("confirmed_delete_date_confirm", False)
        to_delete = st.session_state.pop("chosen_delete_date_choice", None)  # see take_removal
        if delete_clicked:
            if not confirmed:
                st.error(t("tick_to_confirm", lang()))
            else:
                with write_errors("action_delete_receipt"):
                    removed = db.delete_history_date(user_id, to_delete)
                    if removed:
                        flash("success", t("deleted_rows", lang(), count=removed, date=to_delete))
                    else:
                        flash("info", t("date_already_deleted", lang(), date=to_delete))
                    st.rerun()


def render_history_list(user_id, history, start_date, end_date):
    """The purchases of the period, where only the category can be changed (see core/history.py).

    The editor is in a form, so edits are sent together with "Save changes".
    Its key holds the period, the language and history_version (bumped after
    saving), so the edits of one list are never applied to another.
    The editor reports edits by row position, so the rows it showed are kept
    in history_shown. On the run "Save changes" sends, the editor gets that
    same list again and the edits are mapped on it, not on the one loaded
    again in this run: that one may have lost rows (deleted in another tab),
    which would move the others, and Streamlit drops edits of rows that are
    no longer there. Saving bumps history_version, so the next run shows the
    list as it is now.
    """
    categories = load(db.get_categories, user_id, what="what_categories")
    editor_key = f"history_editor_{lang()}_{start_date}_{end_date}_{st.session_state.history_version}"
    shown_before = st.session_state.get("history_shown")
    saving = st.session_state.get("history_save", False)  # the submit button's value on its own run
    shown = shown_before[1] if saving and shown_before and shown_before[0] == editor_key else history
    st.session_state.history_shown = (editor_key, shown)
    with st.expander(t("show_all_purchases", lang())):
        st.caption(t("change_category_hint", lang()))
        with st.form("history_form", border=False):
            st.data_editor(
                draft_ops.with_category_labels(shown, lang()),
                key=editor_key,
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                column_order=["Date", "Item", "Price", "Category"],
                disabled=["Date", "Item", "Price"],
                column_config={
                    "Date": st.column_config.TextColumn(t("col_date", lang())),
                    "Item": st.column_config.TextColumn(t("col_item", lang())),
                    "Price": st.column_config.NumberColumn(t("col_price", lang()), format=PRICE_INPUT_FORMAT),
                    "Category": st.column_config.SelectboxColumn(
                        t("col_category", lang()),
                        options=[category_label(name, lang()) for name in categories],
                        required=True,
                    ),
                },
            )
            save_clicked = st.form_submit_button(t("save_category_changes", lang()), key="history_save")
    if save_clicked:
        with write_errors("action_change_categories"):
            result = history_service.change_categories(
                user_id, shown, st.session_state.get(editor_key, {}), lang()
            )
            st.session_state.history_version += 1
            if result.missing:
                flash("warning", t("categories_changed_some_gone", lang(), count=result.changed, gone=result.missing))
            elif result.changed:
                flash("success", t("categories_changed", lang(), count=result.changed))
            else:
                flash("info", t("no_category_changes", lang()))
            st.rerun()


def keep_history_filter():
    """on_change for the category filter: remember the choice and rebuild the history list."""
    st.session_state.history_categories = list(st.session_state.history_filter)
    st.session_state.history_version += 1  # the list shows other rows now


def render_history_filter(user_id, history):
    """Multiselect for showing only some categories; returns the categories it offers.

    The choice (stored names) is kept in history_categories, so it stays
    when the period or the language changes. The options depend on the
    period (categories removed since only show up where they were used), so
    a choice that is not offered now is left out of the widget.
    """
    categories = load(db.get_categories, user_id, what="what_categories")
    options = filter_categories(categories, history)
    chosen = [name for name in st.session_state.history_categories if name in options]
    st.session_state.history_categories = chosen
    st.session_state.history_filter = chosen
    # Labels worked out here: AppTest calls format_func outside a run, where lang() is unavailable.
    labels = {name: category_label(name, lang()) for name in options}
    st.multiselect(
        t("history_filter_label", lang()),
        options=options,
        format_func=labels.__getitem__,
        placeholder=t("history_filter_all", lang()),
        key="history_filter",
        on_change=keep_history_filter,
    )
    return options


def render_history_tab():
    """Tab 2: total spent and spending per category for a period."""
    user_id = st.session_state.current_user
    today = date.today()

    col_start, col_end = st.columns(2)
    start_date = col_start.date_input(t("start_date", lang()), value=today.replace(day=1), format="YYYY-MM-DD")
    end_date = col_end.date_input(t("end_date", lang()), value=today, format="YYYY-MM-DD")

    if start_date > end_date:
        st.error(t("start_after_end", lang()))
        return

    period_history = load(db.get_history, user_id, start_date, end_date, what="what_history")
    options = render_history_filter(user_id, period_history)
    chosen = st.session_state.history_categories
    history = filter_by_categories(period_history, chosen)
    if period_history.empty:
        st.info(t("no_purchases_period", lang()))
    elif history.empty:
        st.info(t("no_purchases_filtered", lang()))
    else:
        col_total, col_count = st.columns(2)
        col_total.metric(t("total_spent", lang()), format_amount(total_cost(history), lang()))
        col_count.metric(t("purchases", lang()), format_number(len(history), lang()))
        if chosen:
            st.caption(t("history_filter_active", lang(), shown=len(chosen), total=len(options)))

        # The chart's tooltip shows the column names, so they are named in the user's language.
        category_column, amount_column = t("col_category", lang()), t("chart_amount", lang())
        by_category = (
            sum_by_category(history)
            .rename(index=lambda name: category_label(name, lang()), columns={"Price": amount_column})
            .rename_axis(category_column)
        )
        st.subheader(t("spending_per_category", lang()))
        st.bar_chart(
            # y is the value column ("kr"), also when the bars are horizontal.
            by_category, y=amount_column, x_label=category_column, y_label="kr",
            horizontal=True, sort=f"-{amount_column}",
        )

        render_history_list(user_id, history, start_date, end_date)

    render_delete_date(user_id)
    render_backup(user_id)
