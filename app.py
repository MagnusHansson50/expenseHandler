"""ExpenseHandler - Streamlit UI.

Run with: python -m streamlit run app.py
"""

from datetime import date

import pandas as pd
import streamlit as st

from core.calculator import sum_by_category, total_cost
from core.constants import FALLBACK_CATEGORY, RECEIPT_COLUMNS
from core.parser import read_receipt
from integrations import db


def empty_receipt():
    return normalize_receipt(pd.DataFrame(columns=RECEIPT_COLUMNS))


def normalize_receipt(df):
    """Give the receipt a clean index and stable dtypes for st.data_editor."""
    df = df.reindex(columns=RECEIPT_COLUMNS).reset_index(drop=True)
    return df.astype({"Item": "object", "Price": "float64", "Category": "object"})


@st.cache_resource
def setup_database():
    """Create the database tables once per server process."""
    db.init_db()
    return True


def init_session_state():
    """Set default values for everything the app keeps between reruns."""
    defaults = {
        "current_user": None,
        "receipt_df": empty_receipt(),
        "table_version": 0,
        "upload_version": 0,
        "purchase_date": date.today(),
        "date_version": 0,
        "flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def switch_user(user_id):
    """Select a user and drop the previous user's unsaved receipt."""
    st.session_state.current_user = user_id
    set_receipt(empty_receipt())
    set_purchase_date(date.today())


def set_purchase_date(value):
    """Set the date shown in the date picker; a new key makes the picker show it."""
    st.session_state.purchase_date = value
    st.session_state.date_version += 1


def date_key():
    return f"purchase_date_{st.session_state.date_version}"


def remember_picked_date():
    """on_change for the date picker: keep the user's own choice."""
    st.session_state.purchase_date = st.session_state[date_key()]


def set_receipt(df):
    """Replace the receipt and give st.data_editor a fresh key so it redraws."""
    st.session_state.receipt_df = normalize_receipt(df)
    st.session_state.table_version += 1


def add_to_receipt(rows):
    receipt = st.session_state.receipt_df
    if receipt.empty:
        set_receipt(rows)
    else:
        set_receipt(pd.concat([receipt, rows], ignore_index=True))


def editor_key():
    return f"receipt_editor_{st.session_state.table_version}"


def apply_editor_changes():
    """on_change for st.data_editor: fold its edits into receipt_df.

    The editor reports changes relative to the data it was given, so they are
    applied to receipt_df and the key is bumped. This keeps one source of truth
    and avoids edits being applied twice on the next rerun.
    """
    changes = st.session_state[editor_key()]
    df = st.session_state.receipt_df.copy()

    for row, values in changes["edited_rows"].items():
        for column, value in values.items():
            df.at[int(row), column] = value
    df = df.drop(index=changes["deleted_rows"])
    if changes["added_rows"]:
        added = pd.DataFrame(changes["added_rows"], columns=RECEIPT_COLUMNS)
        df = pd.concat([df, added], ignore_index=True)

    set_receipt(df)


def flash(kind, message):
    """Show a message after the next rerun (st.rerun would hide it otherwise)."""
    st.session_state.flash = (kind, message)


def show_flash():
    if st.session_state.flash:
        kind, message = st.session_state.flash
        getattr(st, kind)(message)
        st.session_state.flash = None


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


def render_category_manager(user_id, categories):
    """Expander with forms to add and remove the user's categories."""
    with st.expander("⚙️ Manage categories"):
        col_add, col_delete = st.columns(2)

        with col_add:
            with st.form("add_category_form", clear_on_submit=True):
                new_category = st.text_input("New category")
                add_clicked = st.form_submit_button("➕ Add")
            if add_clicked:
                if db.add_category(user_id, new_category):
                    flash("success", f"Added category '{new_category.strip()}'.")
                    st.rerun()
                st.error("Enter a name that is not already in the list.")

        with col_delete:
            removable = [c for c in categories if c != FALLBACK_CATEGORY]
            with st.form("delete_category_form"):
                to_delete = st.selectbox("Category to remove", options=removable)
                delete_clicked = st.form_submit_button("🗑️ Remove")
            if delete_clicked and to_delete:
                db.delete_category(user_id, to_delete)
                flash("success", f"Removed category '{to_delete}'.")
                st.rerun()


def render_manual_entry(categories):
    """Form for adding a purchase by hand."""
    with st.expander("✍️ Add a purchase manually"):
        with st.form("manual_entry_form", clear_on_submit=True):
            col_item, col_price, col_category = st.columns([2, 1, 1])
            item = col_item.text_input("Item")
            price = col_price.number_input("Price (kr)", step=1.0, format="%.2f")
            category = col_category.selectbox(
                "Category",
                options=categories,
                index=categories.index(FALLBACK_CATEGORY) if FALLBACK_CATEGORY in categories else 0,
            )
            submitted = st.form_submit_button("➕ Add to list")
        if submitted:
            if not item.strip():
                st.error("Enter an item description.")
            else:
                add_to_receipt(pd.DataFrame([{"Item": item.strip(), "Price": price, "Category": category}]))
                st.rerun()


def render_pdf_upload(user_id):
    """Upload an ICA receipt, parse it and pre-fill categories from memory."""
    uploaded = st.file_uploader(
        "Upload an ICA receipt (.pdf)",
        type="pdf",
        key=f"pdf_upload_{st.session_state.upload_version}",
    )
    if uploaded is None:
        return

    try:
        items, receipt_date = read_receipt(uploaded.getvalue())
    except Exception as error:  # PyPDF2 raises many different errors for broken files
        st.error(f"Could not read the PDF: {error}")
        return

    # A new key empties the uploader, so the same file is not parsed again on rerun.
    st.session_state.upload_version += 1
    if items.empty:
        flash("warning", "No items were found in the PDF.")
    else:
        memory = db.load_memory(user_id)
        items["Category"] = items["Item"].map(memory).fillna(FALLBACK_CATEGORY)
        add_to_receipt(items)
        remembered = items["Item"].isin(memory.keys()).sum()
        message = f"Added {len(items)} items ({remembered} categorized from memory)."
        if receipt_date:
            set_purchase_date(receipt_date)
            message += f" Purchase date set to {receipt_date:%Y-%m-%d} from the receipt."
        else:
            message += " No date found on the receipt; check the purchase date."
        flash("success", message)
    st.rerun()


def render_receipt_editor(categories):
    """Editable table of the current receipt."""
    receipt = st.session_state.receipt_df
    # Keep categories that were deleted after being assigned, so they still display.
    options = sorted(set(categories) | set(receipt["Category"].dropna()), key=str.lower)

    st.data_editor(
        receipt,
        key=editor_key(),
        on_change=apply_editor_changes,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Item": st.column_config.TextColumn("Item", required=True),
            "Price": st.column_config.NumberColumn("Price (kr)", format="%.2f", required=True),
            "Category": st.column_config.SelectboxColumn("Category", options=options, required=True),
        },
    )


def render_save_section(user_id):
    """Pick a date and save the receipt to history; learn categories into memory."""
    receipt = st.session_state.receipt_df

    col_date, col_save, col_clear = st.columns([2, 1, 1], vertical_alignment="bottom")
    purchase_date = col_date.date_input(
        "Purchase date",
        value=st.session_state.purchase_date,
        key=date_key(),
        on_change=remember_picked_date,
        format="YYYY-MM-DD",
    )

    if col_save.button("💾 Save", type="primary", width="stretch"):
        saved = db.save_history(user_id, purchase_date, receipt)
        learned = receipt.dropna(subset=["Item", "Category"])
        db.save_memory(user_id, dict(zip(learned["Item"], learned["Category"])))
        set_receipt(empty_receipt())
        set_purchase_date(date.today())
        flash("success", f"Saved {saved} rows for {purchase_date:%Y-%m-%d}.")
        st.rerun()

    if col_clear.button("🗑️ Clear list", width="stretch"):
        set_receipt(empty_receipt())
        set_purchase_date(date.today())
        st.rerun()


def render_current_receipt_tab():
    """Tab 1: build the current receipt and save it to history."""
    user_id = st.session_state.current_user
    categories = db.get_categories(user_id)

    render_category_manager(user_id, categories)
    render_manual_entry(categories)
    render_pdf_upload(user_id)

    if st.session_state.receipt_df.empty:
        st.info("Add a purchase manually or upload a receipt to get started.")
        return

    st.subheader("Current list")
    render_receipt_editor(categories)
    st.metric("Total", f"{total_cost(st.session_state.receipt_df):.2f} kr")
    render_save_section(user_id)


def render_delete_date(user_id):
    """Expander for removing everything saved on one date."""
    saved_dates = db.get_history_dates(user_id)
    if not saved_dates:
        return

    with st.expander("🗑️ Delete a saved receipt"):
        with st.form("delete_date_form"):
            to_delete = st.selectbox("Date", options=saved_dates)
            confirmed = st.checkbox("Yes, delete every purchase saved on this date")
            delete_clicked = st.form_submit_button("Delete")
        if delete_clicked:
            if not confirmed:
                st.error("Tick the box to confirm.")
            else:
                removed = db.delete_history_date(user_id, to_delete)
                flash("success", f"Deleted {removed} rows from {to_delete}.")
                st.rerun()


def render_history_tab():
    """Tab 2: total spent and spending per category for a period."""
    user_id = st.session_state.current_user
    today = date.today()

    col_start, col_end = st.columns(2)
    start_date = col_start.date_input("Start date", value=today.replace(day=1), format="YYYY-MM-DD")
    end_date = col_end.date_input("End date", value=today, format="YYYY-MM-DD")

    if start_date > end_date:
        st.error("The start date must be on or before the end date.")
        return

    history = db.get_history(user_id, start_date, end_date)
    if history.empty:
        st.info("No purchases saved in this period.")
    else:
        col_total, col_count = st.columns(2)
        col_total.metric("Total spent", f"{total_cost(history):.2f} kr")
        col_count.metric("Purchases", len(history))

        by_category = sum_by_category(history)
        st.subheader("Spending per category")
        st.bar_chart(by_category, y="Price", y_label="kr", horizontal=True, sort="-Price")

        with st.expander("Show all purchases"):
            st.dataframe(
                history.drop(columns="Id"),
                hide_index=True,
                width="stretch",
                column_config={"Price": st.column_config.NumberColumn("Price (kr)", format="%.2f")},
            )

    render_delete_date(user_id)


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
    show_flash()

    tab_receipt, tab_history = st.tabs(["🛒 Current Receipt", "📜 History"])
    with tab_receipt:
        render_current_receipt_tab()
    with tab_history:
        render_history_tab()


main()
