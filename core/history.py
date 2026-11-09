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
