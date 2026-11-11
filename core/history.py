"""Logic for saved purchases (history), as pure functions.

The history list in the UI is a `st.data_editor` where only the category can
be changed. It shows the categories as labels (with_category_labels), so a
category picked there is turned back into its stored name here.
"""

from core.i18n import category_value


def category_changes(history, editor_changes, lang):
    """Return {history id: stored category} for the purchases given another category.

    `history` is the DataFrame shown in the editor (with the columns Id and
    Category, stored names, in the order shown); `editor_changes` is what
    `st.data_editor` reports. Only edited categories count: a category set
    back to what it was, or cleared, is left out. Rows added or deleted in
    the editor are ignored (the list does not allow them).
    """
    changes = {}
    for row, values in editor_changes.get("edited_rows", {}).items():
        shown = values.get("Category")
        if not isinstance(shown, str) or not shown.strip():
            continue
        purchase = history.iloc[int(row)]
        category = category_value(shown, lang)
        if category != purchase["Category"]:
            changes[int(purchase["Id"])] = category
    return changes


def filter_categories(categories, history):
    """The categories the history can be filtered on, as stored names.

    The user's categories in their order, then any other category found in
    `history` (one the user has removed since; saved purchases keep it),
    so those purchases can be found and given a new category.
    """
    known = list(dict.fromkeys(categories))
    older = sorted(set(history["Category"]) - set(known), key=str.casefold)
    return known + older


def filter_by_categories(history, chosen):
    """The purchases in one of the `chosen` categories (stored names).

    Nothing chosen means no filter: every purchase. The result is numbered
    from 0 again, since the history list maps its rows by position
    (see category_changes).
    """
    if not chosen:
        return history
    return history[history["Category"].isin(list(chosen))].reset_index(drop=True)
