"""Translations of user-facing text, and number formatting per language.

Pure Python: no Streamlit. All text the user sees is looked up here with
t(key, lang, **params); code, comments and logs stay in English.

To add a text: add the same key to every language in TRANSLATIONS, with the
same {placeholders}. tests/test_i18n.py fails if a language is missing a key
or a placeholder.
"""

import string

LANGUAGES = {"sv": "Svenska", "en": "English"}
DEFAULT_LANGUAGE = "sv"

TRANSLATIONS = {
    "sv": {
        # Page and navigation
        "app_title": "🧾 ExpenseHandler",
        "language_label": "Språk",
        "select_or_create_user": "Välj eller skapa en användare i sidomenyn för att komma igång.",
        "showing_data_for": "Visar data för **{name}**",
        "tab_receipt": "🛒 Aktuellt kvitto",
        "tab_history": "📜 Historik",
        # Sidebar: users
        "sidebar_user_header": "👤 Användare",
        "select_user": "Välj användare",
        "choose_user_placeholder": "Välj en användare...",
        "no_users_placeholder": "Inga användare än",
        "create_user_label": "Skapa ny användare",
        "create_user_button": "➕ Skapa användare",
        # Categories
        "manage_categories": "⚙️ Hantera kategorier",
        "new_category": "Ny kategori",
        "add_button": "➕ Lägg till",
        "category_added": "Kategorin '{name}' har lagts till.",
        "category_name_invalid": "Ange ett namn på 1–{max} tecken som inte redan finns i listan.",
        "category_to_remove": "Kategori att ta bort",
        "remove_button": "🗑️ Ta bort",
        "category_removed": "Kategorin '{name}' har tagits bort.",
        "category_not_removed": "Kategorin '{name}' kunde inte tas bort.",
        # Manual entry and PDF upload
        "manual_entry": "✍️ Lägg till ett köp manuellt",
        "add_to_list": "➕ Lägg till i listan",
        "item_missing": "Ange en beskrivning av varan.",
        "upload_label": "Ladda upp ett kvitto från ICA (.pdf)",
        "not_a_pdf": "Filen är ingen PDF. Ladda upp kvittot som PDF från ICA.",
        "pdf_unreadable": "Det gick inte att läsa PDF-filen. Kontrollera att det är ett kvitto från ICA och försök igen.",
        "no_items_found": "Inga varor hittades i PDF-filen.",
        "import_added": "{count} varor har lagts till ({remembered} fick kategori från minnet).",
        "import_date_set": "Köpdatumet är satt till {date} från kvittot.",
        "import_no_date": "Inget datum hittades på kvittot; kontrollera köpdatumet.",
        # Draft receipt table and saving
        "empty_draft_info": "Lägg till ett köp manuellt eller ladda upp ett kvitto för att komma igång.",
        "current_list": "Aktuell lista",
        "col_item": "Vara",
        "col_price": "Pris (kr)",
        "col_category": "Kategori",
        "col_date": "Datum",
        "total": "Totalt",
        "purchase_date": "Köpdatum",
        "save_button": "💾 Spara",
        "clear_list": "🗑️ Töm listan",
        "not_saved": "Kvittot sparades inte:",
        "saved_rows": "{count} rader sparades för {date}.",
        # History
        "start_date": "Startdatum",
        "end_date": "Slutdatum",
        "start_after_end": "Startdatumet måste vara samma dag som eller före slutdatumet.",
        "no_purchases_period": "Inga köp är sparade under perioden.",
        "total_spent": "Totalt spenderat",
        "purchases": "Köp",
        "spending_per_category": "Utgifter per kategori",
        "show_all_purchases": "Visa alla köp",
        "delete_receipt_expander": "🗑️ Radera ett sparat kvitto",
        "confirm_delete": "Ja, radera alla köp som sparats detta datum",
        "delete_button": "Radera",
        "tick_to_confirm": "Kryssa i rutan för att bekräfta.",
        "deleted_rows": "{count} rader raderades från {date}.",
        # Database errors: "Kunde inte läsa in <what>" / "Kunde inte <action>"
        "load_failed": "Kunde inte läsa in {what}. Databasen kan vara upptagen.",
        "try_again": "🔄 Försök igen",
        "write_failed": "Kunde inte {action}. Databasen kan vara upptagen – försök igen.",
        "what_database": "databasen",
        "what_users": "användarlistan",
        "what_selected_user": "den valda användaren",
        "what_categories": "dina kategorier",
        "what_memory": "dina sparade kategorival",
        "what_saved_dates": "dina sparade datum",
        "what_history": "din historik",
        "action_create_user": "skapa användaren",
        "action_add_category": "lägga till kategorin",
        "action_remove_category": "ta bort kategorin",
        "action_save_receipt": "spara kvittot",
        "action_delete_receipt": "radera kvittot",
    },
    "en": {
        # Page and navigation
        "app_title": "🧾 ExpenseHandler",
        "language_label": "Language",
        "select_or_create_user": "Select or create a user in the sidebar to get started.",
        "showing_data_for": "Showing data for **{name}**",
        "tab_receipt": "🛒 Current Receipt",
        "tab_history": "📜 History",
        # Sidebar: users
        "sidebar_user_header": "👤 User",
        "select_user": "Select user",
        "choose_user_placeholder": "Choose a user...",
        "no_users_placeholder": "No users yet",
        "create_user_label": "Create new user",
        "create_user_button": "➕ Create user",
        # Categories
        "manage_categories": "⚙️ Manage categories",
        "new_category": "New category",
        "add_button": "➕ Add",
        "category_added": "Added category '{name}'.",
        "category_name_invalid": "Enter a name of 1–{max} characters that is not already in the list.",
        "category_to_remove": "Category to remove",
        "remove_button": "🗑️ Remove",
        "category_removed": "Removed category '{name}'.",
        "category_not_removed": "Category '{name}' could not be removed.",
        # Manual entry and PDF upload
        "manual_entry": "✍️ Add a purchase manually",
        "add_to_list": "➕ Add to list",
        "item_missing": "Enter an item description.",
        "upload_label": "Upload an ICA receipt (.pdf)",
        "not_a_pdf": "The file is not a PDF. Upload the receipt as a PDF from ICA.",
        "pdf_unreadable": "Could not read the PDF. Check that it is an ICA receipt and try again.",
        "no_items_found": "No items were found in the PDF.",
        "import_added": "Added {count} items ({remembered} categorized from memory).",
        "import_date_set": "Purchase date set to {date} from the receipt.",
        "import_no_date": "No date found on the receipt; check the purchase date.",
        # Draft receipt table and saving
        "empty_draft_info": "Add a purchase manually or upload a receipt to get started.",
        "current_list": "Current list",
        "col_item": "Item",
        "col_price": "Price (kr)",
        "col_category": "Category",
        "col_date": "Date",
        "total": "Total",
        "purchase_date": "Purchase date",
        "save_button": "💾 Save",
        "clear_list": "🗑️ Clear list",
        "not_saved": "The receipt was not saved:",
        "saved_rows": "Saved {count} rows for {date}.",
        # History
        "start_date": "Start date",
        "end_date": "End date",
        "start_after_end": "The start date must be on or before the end date.",
        "no_purchases_period": "No purchases saved in this period.",
        "total_spent": "Total spent",
        "purchases": "Purchases",
        "spending_per_category": "Spending per category",
        "show_all_purchases": "Show all purchases",
        "delete_receipt_expander": "🗑️ Delete a saved receipt",
        "confirm_delete": "Yes, delete every purchase saved on this date",
        "delete_button": "Delete",
        "tick_to_confirm": "Tick the box to confirm.",
        "deleted_rows": "Deleted {count} rows from {date}.",
        # Database errors: "Could not load <what>" / "Could not <action>"
        "load_failed": "Could not load {what}. The database may be busy.",
        "try_again": "🔄 Try again",
        "write_failed": "Could not {action}. The database may be busy; please try again.",
        "what_database": "the database",
        "what_users": "the list of users",
        "what_selected_user": "the selected user",
        "what_categories": "your categories",
        "what_memory": "your remembered categories",
        "what_saved_dates": "your saved dates",
        "what_history": "your history",
        "action_create_user": "create the user",
        "action_add_category": "add the category",
        "action_remove_category": "remove the category",
        "action_save_receipt": "save the receipt",
        "action_delete_receipt": "delete the receipt",
    },
}

# Non-breaking space: keeps "1 122,17 kr" on one line.
_NBSP = " "


def resolve_language(lang):
    """Return `lang` if it is supported, otherwise DEFAULT_LANGUAGE."""
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def t(key, lang, **params):
    """Return the text for `key` in `lang`, with {placeholders} filled from `params`.

    An unsupported language falls back to DEFAULT_LANGUAGE. An unknown key or
    a missing parameter raises KeyError: a missing text is a bug, and the
    tests check that every key used exists in every language.
    """
    text = TRANSLATIONS[resolve_language(lang)][key]
    return text.format(**params) if params else text


def placeholders(text):
    """Return the set of {placeholder} names used in a text."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def format_amount(value, lang):
    """Format an amount in kronor for display.

    Swedish: "1 122,17 kr" (space between thousands, decimal comma).
    English: "1,122.17 kr" (comma between thousands, decimal point).
    """
    rounded = round(float(value), 2)
    if rounded == 0:
        rounded = 0.0  # avoid "-0,00 kr"
    number = f"{rounded:,.2f}"  # e.g. "-1,122.17"
    if resolve_language(lang) == "sv":
        number = number.replace(",", _NBSP).replace(".", ",")
    return f"{number}{_NBSP}kr"
