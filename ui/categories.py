""""Manage categories": adding (with the look-alike question) and removing categories.
add_category and remove_category are shared with the review popup.
"""

import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from core.categories import category_clash, name_problem
from core.constants import FALLBACK_CATEGORY, MAX_NAME_LENGTH
from core.i18n import t
from core.text import escape_markdown
from integrations import db
from ui.common import flash, lang, take_removal, write_errors
from ui.draft import set_draft


def render_category_manager(user_id, categories):
    """Expander with forms to add and remove the user's categories."""
    with st.expander(t("manage_categories", lang())):
        col_add, col_delete = st.columns(2)

        with col_add:
            with st.form("add_category_form", clear_on_submit=True):
                new_category = st.text_input(t("new_category", lang()), max_chars=MAX_NAME_LENGTH)
                add_clicked = st.form_submit_button(t("add_button", lang()))
            if add_clicked:
                st.session_state.pending_category = None  # a new name replaces an open question
                with write_errors("action_add_category"):
                    kind, message = add_category(user_id, new_category, categories)
                    if kind == "success":
                        flash(kind, message)
                        st.rerun()
                    if kind == "similar":
                        # Asked below; the name waits in session state for the answer.
                        st.session_state.pending_category = (new_category.strip(), message)
                    else:
                        st.error(message)
            render_similar_category_question(user_id, categories)

        with col_delete:
            removable = [c for c in categories if c != FALLBACK_CATEGORY]
            with st.form("delete_category_form"):
                st.selectbox(t("category_to_remove", lang()), options=removable, key="category_remove_choice")
                st.caption(t("remove_category_note", lang()))
                st.checkbox(t("remove_category_confirm", lang()), key="category_remove_confirm")
                delete_clicked = st.form_submit_button(
                    t("remove_button", lang()), on_click=take_removal,
                    args=("category_remove_confirm", "category_remove_choice"),
                )
            confirmed = st.session_state.pop("confirmed_category_remove_confirm", False)
            to_delete = st.session_state.pop("chosen_category_remove_choice", None)  # see take_removal
            if delete_clicked and to_delete and not confirmed:
                st.error(t("tick_to_confirm", lang()))
            elif delete_clicked and to_delete:
                with write_errors("action_remove_category"):
                    kind, message = remove_category(user_id, to_delete)
                    if kind == "success":
                        flash(kind, message)
                        st.rerun()
                    st.error(message)


def add_category(user_id, name, categories, confirmed=False):
    """Add a category for the user; returns (kind, message) to show. Run it inside write_errors.

    Used by "Manage categories" and by the review popup, so both follow the
    same rules (db.add_category: length, no duplicates, no reserved names).
    A name the user already has is refused with its own message. A name that
    only differs from an existing category in letter case or spacing ("mjölk"
    next to "Mjölk") is not added until the user confirms it: then kind is
    "similar" and message is the existing category's name (not escaped).
    """
    problem = name_problem(name)
    if problem:
        params = {key: escape_markdown(value) if isinstance(value, str) else value
                  for key, value in problem.params.items()}
        return "error", t(problem.key, lang(), **params)
    clash = category_clash(name, categories)
    if clash and clash.exact:
        return "error", t("category_exists", lang(), name=escape_markdown(clash.existing))
    if clash and not confirmed:
        return "similar", clash.existing
    if db.add_category(user_id, name):
        return "success", t("category_added", lang(), name=escape_markdown(name.strip()))
    # The name was allowed above, so it was added in another tab in the meantime.
    return "error", t("category_exists", lang(), name=escape_markdown(name.strip()))


def render_similar_category_question(user_id, categories):
    """Ask whether to add a name that looks like an existing category, if one is waiting.

    The answer is an active choice: "Add anyway" adds it, "Cancel" forgets it.
    """
    pending = st.session_state.pending_category
    if not pending:
        return
    name, existing = pending
    st.warning(t("category_similar", lang(), name=escape_markdown(name), existing=escape_markdown(existing)))
    col_yes, col_no = st.columns(2)
    if col_yes.button(t("category_add_anyway", lang()), key="add_similar_category"):
        with write_errors("action_add_category"):
            kind, message = add_category(user_id, name, categories, confirmed=True)
            st.session_state.pending_category = None
            if kind == "success":
                flash(kind, message)
                st.rerun()
            st.error(message)
    if col_no.button(t("cancel_button", lang()), key="cancel_similar_category"):
        st.session_state.pending_category = None
        st.rerun()


def remove_category(user_id, name):
    """Remove one of the user's categories; returns (kind, message) to show. Run it inside write_errors.

    Used by "Manage categories" and by the review popup. db.delete_category
    also forgets the remembered choices pointing at it and refuses the
    fallback category; saved purchases keep it.
    """
    if db.delete_category(user_id, name):
        # Rows of the unsaved receipt in that category show the fallback category now.
        set_draft(draft_ops.clear_category(st.session_state.receipt_df, name))
        return "success", t("category_removed", lang(), name=escape_markdown(name))
    return "error", t("category_not_removed", lang(), name=escape_markdown(name))
