"""The user's own settings, in a collapsed "Settings" section of the sidebar.

So far only the highest price per item ("max amount"): it catches typing
mistakes (15900 for 159,00), and a user who buys something more expensive
can raise it, within MAX_PRICE_SETTING_MIN..MAX_PRICE_CEILING.
"""

import streamlit as st

from core.constants import MAX_PRICE_CEILING, MAX_PRICE_SETTING_MIN
from core.i18n import format_amount, t
from core.settings import max_price_problem
from integrations import db
from ui.common import PRICE_INPUT_FORMAT, flash, lang, load, write_errors


def render_settings(user_id):
    """The Settings section: the highest price per item and a save button.

    Saving affects only this user, and from the next check on: a receipt
    being edited is checked against the new limit when it is saved.
    """
    max_price = load(db.get_max_price, user_id, what="what_settings")
    with st.expander(t("settings_header", lang())):
        with st.form("settings_form", border=False):
            new_max_price = st.number_input(
                t("max_price_label", lang()),
                min_value=float(MAX_PRICE_SETTING_MIN),
                max_value=float(MAX_PRICE_CEILING),
                value=float(max_price),
                step=1000.0,
                format=PRICE_INPUT_FORMAT,
                key="settings_max_price",
            )
            st.caption(t("max_price_help", lang(), min=MAX_PRICE_SETTING_MIN, max=MAX_PRICE_CEILING))
            saved = st.form_submit_button(t("settings_save_button", lang()))
        if saved:
            problem = max_price_problem(new_max_price)
            if problem:
                st.error(t(problem.key, lang(), **problem.params))
                return
            with write_errors("action_save_settings"):
                db.set_max_price(user_id, new_max_price)
                flash("success", t("max_price_saved", lang(), max=format_amount(new_max_price, lang())))
                st.rerun()
