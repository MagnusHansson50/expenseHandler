"""Tab "Current Receipt": manual entry, PDF upload, the editable list, removing an item, the
comparison with the amount paid, and saving.
"""

import logging
from datetime import date

import pandas as pd
import streamlit as st

from core import receipt as draft_ops  # the draft receipt being edited
from core.calculator import paid_difference, total_cost
from core.constants import FALLBACK_CATEGORY, MAX_ITEM_LENGTH, MAX_PRICE
from core.i18n import category_label, category_value, format_amount, t
from core.parser import NotAPdfError, ReceiptReadError, UnknownReceiptFormat
from integrations import db
from services import receipts
from ui.categories import render_category_manager
from ui.common import PRICE_INPUT_FORMAT, flash, lang, load, write_errors
from ui.draft import (
    add_to_draft,
    date_key,
    editor_key,
    note_removed,
    on_editor_change,
    remember_picked_date,
    set_draft,
    set_purchase_date,
)
from ui.review import render_review, start_review

logger = logging.getLogger(__name__)


def render_manual_entry(categories, header):
    """Form for adding a purchase by hand: above the upload while the list is empty, then below the table."""
    with st.expander(header):
        with st.form("manual_entry_form", clear_on_submit=True):
            col_item, col_price, col_category = st.columns([2, 1, 1])
            item = col_item.text_input(t("col_item", lang()), max_chars=MAX_ITEM_LENGTH)
            price = col_price.number_input(
                t("col_price", lang()),
                min_value=float(-MAX_PRICE),
                max_value=float(MAX_PRICE),
                value=None,  # empty, so a forgotten price is caught; 0 typed in is a gift
                step=1.0,
                format=PRICE_INPUT_FORMAT,
            )
            # Options are the labels as shown ("Övrigt"); category_value maps the choice back.
            labels = [category_label(name, lang()) for name in categories]
            fallback_label = category_label(FALLBACK_CATEGORY, lang())
            category_shown = col_category.selectbox(
                t("col_category", lang()),
                options=labels,
                index=labels.index(fallback_label) if fallback_label in labels else 0,
            )
            submitted = st.form_submit_button(t("add_to_list", lang()))
        if submitted:
            if not item.strip():
                st.error(t("item_missing", lang()))
            elif price is None:
                # The field starts empty. 0 kr typed in is allowed (a gift), and so are
                # negative amounts (discounts).
                st.error(t("price_missing", lang()))
            else:
                category = category_value(category_shown, lang())
                add_to_draft(pd.DataFrame([{"Item": item.strip(), "Price": price, "Category": category}]))
                st.rerun()


def render_pdf_upload(user_id, categories):
    """Upload a receipt PDF (Kivra or Willys), parse it and pre-fill categories from memory."""
    uploaded = st.file_uploader(
        t("upload_label", lang()),
        type="pdf",
        key=f"pdf_upload_{st.session_state.upload_version}",
    )
    if uploaded is None:
        return

    try:
        # A database error here goes through load(): the file stays in the
        # uploader and "Try again" imports it again.
        result = load(
            receipts.import_receipt, user_id, uploaded.getvalue(), categories,
            what="what_memory",
        )
    except NotAPdfError:
        st.error(t("not_a_pdf", lang()))
        return
    except UnknownReceiptFormat:
        # Expected for other PDFs; nothing to log (the file may hold personal data).
        st.error(t("unknown_receipt_format", lang()))
        return
    except ReceiptReadError:
        # The pypdf error is logged for debugging but not shown to the user.
        # Any other exception is a bug in our code and is left to Streamlit,
        # which logs the full traceback and shows a generic error.
        logger.warning("Could not read an uploaded PDF", exc_info=True)
        st.error(t("pdf_unreadable", lang()))
        return

    # A new key empties the uploader, so the same file is not imported again on rerun.
    st.session_state.upload_version += 1
    if result.items.empty:
        flash("warning", t("no_items_found", lang()))
    else:
        # The amount paid to compare the list with while editing (render_paid_comparison):
        # this receipt's, added to the earlier receipts' in the same list. Items that were
        # already there without a paid amount make a comparison meaningless.
        earlier = st.session_state.paid_total
        if st.session_state.receipt_df.empty:
            paid = result.paid_total
        elif earlier is not None and result.paid_total is not None:
            paid = round(earlier + result.paid_total, 2)
        else:
            paid = None
        add_to_draft(result.items)
        st.session_state.paid_total = paid
        # Which rows came from receipts, so removing one counts as removed on purpose (note_removed).
        st.session_state.imported_rows = (
            st.session_state.imported_rows
            + [[item, price] for item, price in zip(result.items["Item"], result.items["Price"], strict=True)]
            if paid is not None else []
        )
        if result.purchase_date:
            set_purchase_date(result.purchase_date)
        notice = import_message(result)
        flash(*notice)
        if result.remembered < len(result.items):
            # Some items got no category from memory: open the review popup by
            # itself (adding items by hand does not, see render_review). The
            # popup covers the flash, so it shows the import message itself.
            start_review()
            st.session_state.review_notice = notice
    st.rerun()


def import_message(result):
    """(kind, text) shown after a receipt PDF has been imported.

    A warning instead of a success when the items do not add up to the
    receipt's paid total, so missing or misread items are noticed.
    """
    parts = [t("import_added", lang(), count=len(result.items), remembered=result.remembered)]
    if result.purchase_date:
        parts.append(t("import_date_set", lang(), date=f"{result.purchase_date:%Y-%m-%d}"))
    else:
        parts.append(t("import_no_date", lang()))
    difference = paid_difference(result.items, result.paid_total)
    if difference is None:
        return "success", " ".join(parts)
    parts.append(t(
        "paid_items_missing" if difference > 0 else "paid_items_too_much", lang(),
        paid_total=format_amount(result.paid_total, lang()),
        difference=format_amount(abs(difference), lang()),
        removed="",
    ))
    return "warning", " ".join(parts)


def render_receipt_editor(categories):
    """Editable table of the current receipt."""
    # The editor shows category labels ("Övrigt"); on_editor_change maps them back.
    shown = draft_ops.with_category_labels(st.session_state.receipt_df, lang())
    labels = {category_label(name, lang()) for name in categories}
    # Keep categories that were deleted after being assigned, so they still display.
    options = sorted(labels | set(shown["Category"].dropna()), key=str.lower)

    st.data_editor(
        shown,
        key=editor_key(),
        on_change=on_editor_change,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Item": st.column_config.TextColumn(t("col_item", lang()), required=True, max_chars=MAX_ITEM_LENGTH),
            "Price": st.column_config.NumberColumn(
                t("col_price", lang()),
                format=PRICE_INPUT_FORMAT,
                required=True,
                min_value=-MAX_PRICE,
                max_value=MAX_PRICE,
            ),
            "Category": st.column_config.SelectboxColumn(
                t("col_category", lang()), options=options, required=True
            ),
        },
    )


def remove_chosen_row(widget_key):
    """on_click for "Remove": drop the chosen row from the draft (never saved, never remembered)."""
    row = st.session_state.get(widget_key)
    draft = st.session_state.receipt_df
    if row is not None and 0 <= row < len(draft):
        note_removed(draft.iloc[[row]])
        set_draft(draft_ops.remove_row(draft, row))


def render_remove_item():
    """A plain way to remove a row from the draft, e.g. something bought for someone else.

    Rows are listed with their number, so two rows with the same name can be told apart.
    The key holds table_version, so the list starts over whenever the draft changes.
    """
    draft = st.session_state.receipt_df
    widget_key = f"remove_row_{st.session_state.table_version}"
    labels = [
        t(
            "remove_item_option", lang(), row=number,
            item=item if isinstance(item, str) else "",
            amount=format_amount(price, lang()) if pd.notna(price) else "",
        )
        for number, (item, price) in enumerate(zip(draft["Item"], draft["Price"], strict=True), 1)
    ]
    with st.expander(t("remove_item_header", lang())):
        st.caption(t("remove_item_note", lang()))
        col_choice, col_button = st.columns([3, 1], vertical_alignment="bottom")
        col_choice.selectbox(
            t("remove_item_choice", lang()),
            options=list(range(len(draft))),
            format_func=labels.__getitem__,  # the row's number, name and amount
            key=widget_key,
        )
        col_button.button(
            t("remove_button", lang()), key="remove_item", width="stretch",
            on_click=remove_chosen_row, args=(widget_key,),
        )


def render_save_section(user_id):
    """Pick a date and save the receipt to history; learn categories into memory."""
    draft = st.session_state.receipt_df

    col_date, col_save, col_clear = st.columns([2, 1, 1], vertical_alignment="bottom")
    purchase_date = col_date.date_input(
        t("purchase_date", lang()),
        value=st.session_state.purchase_date,
        key=date_key(),
        on_change=remember_picked_date,
        format="YYYY-MM-DD",
    )

    if col_save.button(t("save_button", lang()), type="primary", width="stretch"):
        with write_errors("action_save_receipt"):
            try:
                saved = receipts.save_receipt(
                    user_id, purchase_date, draft, st.session_state.review_kept_fallback
                )
            except receipts.InvalidReceipt as error:
                problems = "\n".join(f"- {t(p.key, lang(), **p.params)}" for p in error.problems)
                st.error(f"{t('not_saved', lang())}\n\n{problems}")
                return
            set_draft(draft_ops.empty_receipt())
            set_purchase_date(date.today())
            flash("success", t("saved_rows", lang(), count=saved, date=f"{purchase_date:%Y-%m-%d}"))
            st.rerun()

    if col_clear.button(t("clear_list", lang()), width="stretch"):
        set_draft(draft_ops.empty_receipt())
        set_purchase_date(date.today())
        st.rerun()


def render_current_receipt_tab():
    """Tab 1: build the current receipt and save it to history."""
    user_id = st.session_state.current_user
    categories = load(db.get_categories, user_id, what="what_categories")

    render_category_manager(user_id, categories)
    if st.session_state.receipt_df.empty:
        render_manual_entry(categories, t("manual_entry", lang()))
    render_pdf_upload(user_id, categories)

    if st.session_state.receipt_df.empty:
        st.info(t("empty_draft_info", lang()))
        return

    st.subheader(t("current_list", lang()))
    render_review(user_id, categories)
    st.caption(t("receipt_table_hint", lang()))
    render_receipt_editor(categories)
    # Next to the table, so a missing item is added where the list is checked.
    render_manual_entry(categories, t("add_missing_item", lang()))
    render_remove_item()
    total = total_cost(st.session_state.receipt_df)
    st.metric(t("total", lang()), format_amount(total, lang()))
    render_paid_comparison()
    render_save_section(user_id)


def render_paid_comparison():
    """How the list compares with the amount paid on the uploaded receipt(s), while editing."""
    paid = st.session_state.paid_total
    if paid is None:
        return
    # Items removed on purpose (bought for someone else) are not missing.
    removed = st.session_state.removed_total
    difference = paid_difference(st.session_state.receipt_df, round(paid - removed, 2))
    params = {
        "paid_total": format_amount(paid, lang()),
        "removed": t("paid_removed_part", lang(), amount=format_amount(removed, lang())) if removed else "",
    }
    if difference is None:
        st.caption(t("paid_matches", lang(), **params))
    elif difference > 0:
        st.warning(t("paid_items_missing", lang(), difference=format_amount(difference, lang()), **params))
    else:
        st.warning(t("paid_items_too_much", lang(), difference=format_amount(-difference, lang()), **params))
