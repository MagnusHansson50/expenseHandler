"""ExpenseHandler - Streamlit UI.

Run with: python -m streamlit run app.py
"""

import pandas as pd
import streamlit as st

from integrations import db

RECEIPT_COLUMNS = ["Item", "Price", "Category"]


@st.cache_resource
def setup_database():
    """Create the database tables once per server process."""
    db.init_db()
    return True


def init_session_state():
    """Set default values for everything the app keeps between reruns."""
    defaults = {
        "current_user": None,
        "receipt_df": pd.DataFrame(columns=RECEIPT_COLUMNS),
        "table_version": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def switch_user(user_id):
    """Select a user and drop the previous user's unsaved receipt."""
    st.session_state.current_user = user_id
    st.session_state.receipt_df = pd.DataFrame(columns=RECEIPT_COLUMNS)
    st.session_state.table_version += 1


def render_user_sidebar():
    """Sidebar for selecting an existing user or creating a new one."""
    with st.sidebar:
        st.header("👤 User")

        users = db.get_users()
        user_names = dict(users)
        user_ids = list(user_names)
        current = st.session_state.current_user

        selected = st.selectbox(
            "Select user",
            options=user_ids,
            format_func=user_names.get,
            index=user_ids.index(current) if current in user_ids else None,
            placeholder="Choose a user..." if users else "No users yet",
        )
        if selected != current:
            switch_user(selected)
            st.rerun()

        with st.form("create_user_form", clear_on_submit=True):
            new_name = st.text_input("Create new user")
            submitted = st.form_submit_button("➕ Create user")
        if submitted:
            try:
                new_id = db.create_user(new_name)
            except ValueError as error:
                st.error(str(error))
            else:
                switch_user(new_id)
                st.rerun()


def render_current_receipt_tab():
    """Tab 1: build the current receipt (Phase 5)."""
    st.info("Receipt input is coming in Phase 5.")


def render_history_tab():
    """Tab 2: summaries of saved purchases (Phase 6)."""
    st.info("History is coming in Phase 6.")


def main():
    st.set_page_config(page_title="ExpenseHandler", page_icon="🧾", layout="centered")
    setup_database()
    init_session_state()

    render_user_sidebar()

    st.title("🧾 ExpenseHandler")

    user = db.get_user(st.session_state.current_user) if st.session_state.current_user else None
    if user is None:
        st.info("Select or create a user in the sidebar to get started.")
        st.stop()

    st.caption(f"Showing data for **{user[1]}**")

    tab_receipt, tab_history = st.tabs(["🛒 Current Receipt", "📜 History"])
    with tab_receipt:
        render_current_receipt_tab()
    with tab_history:
        render_history_tab()


main()
