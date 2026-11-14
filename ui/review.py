"""The popup that goes through items without a category (see CLAUDE.md, Reviewing items
without a category).
"""

import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from core.constants import FALLBACK_CATEGORY, MAX_NAME_LENGTH
from core.i18n import category_label, category_value, format_amount, t
from core.text import escape_markdown
from integrations import db
from ui.categories import add_category, remove_category
from ui.common import DataUnavailable, flash, lang, load, take_removal, write_errors
from ui.draft import note_removed, set_draft

# --- Review of items without a category ------------------------------------
# Items that still need a category are gone through in a popup (st.dialog),
# one item at a time: clicking a category tag chooses it and moves on. It
# opens by itself after a PDF upload that left items without a category
# (render_pdf_upload), not when items are added by hand (the form defaults to
# the fallback category, so it would open after every item). Above the table
# a button opens the popup and says how many items are left.
# review_active keeps the popup open across reruns; closing it (Stop or the
# window's X) puts the items left in review_dismissed, so it is not opened by
# itself again for them. review_handled lists the items dealt with in this
# review (given a category, kept in the fallback category on purpose, or
# skipped); review_skipped is the subset that was skipped. review_kept_fallback
# lists items put in the fallback category on purpose: only those are
# remembered as such when the receipt is saved, so items nobody decided on are
# asked about again next time. review_names are the items the open popup is
# about, for the close callback. review_notice is the PDF import message,
# shown at the top of a popup that opened by itself (it covers the flash).


def start_review():
    st.session_state.review_active = True
    st.session_state.review_handled = []
    st.session_state.review_skipped = []
    st.session_state.review_notice = None
    st.session_state.review_category_message = None
    st.session_state.review_pending_category = None


def close_review():
    """Stop or the popup's X: keep what was chosen, and do not open by itself for the items left."""
    st.session_state.review_active = False
    st.session_state.review_pending_category = None  # an unanswered "add anyway?" is dropped
    st.session_state.review_dismissed = st.session_state.review_names


def review_choose(name, widget_key):
    """A category tag was clicked: give every row with that name its category (tag callback)."""
    shown = st.session_state.get(widget_key)
    if shown is None:
        return  # the tag was clicked off
    category = category_value(shown, lang())
    set_draft(draft_ops.set_item_category(st.session_state.receipt_df, name, category))
    st.session_state.review_handled.append(name)
    if category == FALLBACK_CATEGORY:
        st.session_state.review_kept_fallback.append(name)  # a choice: remember it on save


def review_skip(name):
    st.session_state.review_handled.append(name)
    st.session_state.review_skipped.append(name)


def review_remove(name):
    """Remove the item shown from the receipt (every row with that name); the popup moves on.

    Like a choice it is made in a callback, so the popup stays open. If the
    receipt becomes empty, set_draft ends the review and the popup closes.
    """
    draft = st.session_state.receipt_df
    note_removed(draft_ops.item_rows(draft, name))
    set_draft(draft_ops.remove_item(draft, name))


def review_names(user_id, categories):
    """The draft's items that still need a category (see core.receipt.uncategorized_items)."""
    memory = load(db.load_memory, user_id, what="what_memory")
    return [
        name for name in draft_ops.uncategorized_items(st.session_state.receipt_df, memory, categories)
        if name not in st.session_state.review_kept_fallback  # put in the fallback category on purpose
    ]


def render_review(user_id, categories):
    """The button that opens the review popup, and the popup while it is open."""
    names = review_names(user_id, categories)
    st.session_state.review_names = names
    if st.session_state.review_active:
        open_review_dialog(user_id)
    if names and not st.session_state.review_active:
        st.button(
            t("review_open_button", lang(), count=len(names)),
            key="review_open", on_click=start_review,
        )


def finish_review(names):
    """Every item was dealt with: close the popup and say how it went."""
    st.session_state.review_active = False
    st.session_state.review_dismissed = names
    skipped = [name for name in st.session_state.review_skipped if name in names]
    if skipped:
        flash("info", t("review_done_skipped", lang(), count=len(skipped)))
    else:
        flash("success", t("review_done", lang()))
    st.rerun()


def handle_review_category_forms(user_id):
    """Add or remove a category sent from the popup on the previous click.

    A name like an existing category ("mjölk" next to "Mjölk") waits in
    review_pending_category until "Add anyway" or "Cancel" is clicked. Those
    buttons are read here on the click's run, like the forms, so the popup
    stays open and on the same item.
    """
    if st.session_state.get("review_add_submit"):
        st.session_state.review_pending_category = None  # a new name replaces an open question
        name = st.session_state.get("review_new_category", "")
        with write_errors("action_add_category"):
            kind, message = add_category(user_id, name, db.get_categories(user_id))
            if kind == "similar":
                st.session_state.review_pending_category = (name.strip(), message)
            else:
                st.session_state.review_category_message = (kind, message)
    pending = st.session_state.review_pending_category
    if pending and st.session_state.get("review_add_similar"):
        with write_errors("action_add_category"):
            st.session_state.review_category_message = add_category(
                user_id, pending[0], db.get_categories(user_id), confirmed=True,
            )
            st.session_state.review_pending_category = None
    elif pending and st.session_state.get("review_cancel_similar"):
        st.session_state.review_pending_category = None
    to_remove = st.session_state.pop("chosen_review_remove_choice", None)  # see take_removal
    confirmed = st.session_state.pop("confirmed_review_remove_confirm", False)
    if st.session_state.get("review_remove_submit") and to_remove:
        if not confirmed:
            st.session_state.review_category_message = ("error", t("tick_to_confirm", lang()))
            return
        draft = st.session_state.receipt_df
        in_removed = {str(item).strip() for item, category in zip(draft["Item"], draft["Category"], strict=True)
                      if category == to_remove}
        with write_errors("action_remove_category"):
            kind, message = remove_category(user_id, to_remove)
            st.session_state.review_category_message = (kind, message)
            if kind == "success":
                # Items already given that category in this review need one again.
                st.session_state.review_handled = [
                    name for name in st.session_state.review_handled if name not in in_removed
                ]


def open_review_dialog(user_id):
    """Show the popup for the first item that is left."""

    @st.dialog(t("review_title", lang()), width="large", on_dismiss=close_review)
    def review_dialog():
        # A click inside a dialog reruns only this function, so it works out the
        # next item, the categories and any form that was sent from session
        # state and the database by itself, and choices are made in callbacks.
        # The popup then stays open without flickering; the page behind it is
        # updated when it closes (a full rerun).
        if not st.session_state.review_active:  # "Stop" was clicked
            st.rerun()
        try:
            handle_review_category_forms(user_id)
            categories = load(db.get_categories, user_id, what="what_categories")
            names = review_names(user_id, categories)
        except DataUnavailable:
            return  # load() has shown the message and "Try again"
        st.session_state.review_names = names
        handled = len(st.session_state.review_handled)
        pending = [name for name in names if name not in st.session_state.review_handled]
        if not pending:
            finish_review(names)
        name = pending[0]
        total = handled + len(pending)
        widget_key = f"review_category_{handled + 1}"  # a new widget per item, so no choice carries over

        if st.session_state.review_notice:  # what the PDF upload found, e.g. a Betalat mismatch
            kind, message = st.session_state.review_notice
            getattr(st, kind)(message)
        st.progress(handled / total, text=t("review_position", lang(), position=handled + 1, total=total))
        with st.container(border=True):
            col_name, col_amount = st.columns([3, 1], vertical_alignment="center")
            col_name.markdown(f"**{escape_markdown(name)}**")
            col_amount.markdown(format_amount(draft_ops.item_total(st.session_state.receipt_df, name), lang()))
        st.pills(
            t("review_choose_label", lang()),
            options=[category_label(category, lang()) for category in categories],
            selection_mode="single",
            key=widget_key,
            on_change=review_choose,
            args=(name, widget_key),
        )
        with st.form("review_add_category", clear_on_submit=True, border=False):
            col_name, col_add = st.columns([3, 1], vertical_alignment="bottom")
            col_name.text_input(t("new_category", lang()), max_chars=MAX_NAME_LENGTH, key="review_new_category")
            col_add.form_submit_button(t("add_button", lang()), key="review_add_submit")
        if st.session_state.review_pending_category:
            name_new, existing = st.session_state.review_pending_category
            st.warning(t("category_similar", lang(),
                         name=escape_markdown(name_new), existing=escape_markdown(existing)))
            col_yes, col_no = st.columns(2)
            col_yes.button(t("category_add_anyway", lang()), key="review_add_similar")
            col_no.button(t("cancel_button", lang()), key="review_cancel_similar")
        with st.expander(t("review_remove_header", lang())):
            st.caption(t("remove_category_note", lang()))
            with st.form("review_remove_category", border=False):
                st.selectbox(
                    t("category_to_remove", lang()),
                    options=[category for category in categories if category != FALLBACK_CATEGORY],
                    key="review_remove_choice",
                )
                st.checkbox(t("remove_category_confirm", lang()), key="review_remove_confirm")
                st.form_submit_button(
                    t("remove_button", lang()), key="review_remove_submit",
                    on_click=take_removal, args=("review_remove_confirm", "review_remove_choice"),
                )
        if st.session_state.review_category_message:  # shown once
            kind, message = st.session_state.review_category_message
            st.session_state.review_category_message = None
            getattr(st, kind)(message)
        col_skip, col_remove, col_stop = st.columns(3)
        col_skip.button(t("review_skip_button", lang()), key="review_skip", on_click=review_skip, args=(name,))
        col_remove.button(
            t("review_remove_item_button", lang()), key="review_remove_item",
            help=t("review_remove_item_help", lang()), on_click=review_remove, args=(name,),
        )
        col_stop.button(t("review_stop_button", lang()), key="review_stop", on_click=close_review)

    review_dialog()
