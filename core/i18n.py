"""Translations of user-facing text, and number formatting per language.

Pure Python: no Streamlit. All text the user sees is looked up here with
t(key, lang, **params); code, comments and logs stay in English.

To add a text: add the same key to every language in TRANSLATIONS, with the
same {placeholders}. tests/test_i18n.py fails if a language is missing a key
or a placeholder.
"""

import string

from core.constants import FALLBACK_CATEGORY, FALLBACK_CATEGORY_LABELS

LANGUAGES = {"sv": "Svenska", "en": "English"}
DEFAULT_LANGUAGE = "sv"

# Categories a new user starts with, in the language selected when the user
# is created. They are stored as the user's own data and never translated
# afterwards. FALLBACK_CATEGORY is always added on top (see db.create_user).
DEFAULT_CATEGORIES = {
    "sv": ["Mejeri", "Skafferi", "Frukt", "Grönsaker", "Kött & fisk",
           "Bröd", "Fryst", "Dryck", "Snacks", "Hushåll"],
    "en": ["Dairy", "Pantry", "Fruit", "Vegetables", "Meat & Fish",
           "Bread", "Frozen", "Drinks", "Snacks", "Household"],
}

TRANSLATIONS = {
    "sv": {
        # Page and navigation
        "app_title": "🧾 ExpenseHandler",
        "language_label": "Språk",
        "tab_receipt": "🛒 Aktuellt kvitto",
        "tab_history": "📜 Historik",
        # Login and registration
        "login_intro": "Logga in för att se dina kvitton, eller skapa ett konto.",
        "login_tab": "🔐 Logga in",
        "register_tab": "➕ Skapa konto",
        "user_name_label": "Användarnamn",
        "password_label": "Lösenord",
        "repeat_password_label": "Upprepa lösenordet",
        "log_in_button": "Logga in",
        "create_account_button": "Skapa konto",
        "login_failed": "Fel användarnamn eller lösenord.",
        "login_locked": "För många misslyckade försök. Försök igen om {seconds} sekunder.",
        "passwords_differ": "Lösenorden är inte likadana.",
        "logged_in_as": "Inloggad som **{name}**",
        "log_out_button": "🚪 Logga ut",
        "action_log_in": "logga in",
        # Sidebar: users
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
        # Problems from core.receipt.validate_receipt
        "problem_item_missing": "Rad {row}: beskrivning av varan saknas.",
        "problem_item_too_long": "Rad {row}: beskrivningen av varan är längre än {max} tecken.",
        "problem_price_missing": "Rad {row}: priset saknas.",
        "problem_price_out_of_range": "Rad {row}: priset måste vara mellan -{max} och {max} kr.",
        # Rejected user names from db.create_user
        "user_name_empty": "Användarnamnet får inte vara tomt.",
        "user_name_too_long": "Användarnamnet får vara högst {max} tecken.",
        "user_name_taken": "Det finns redan en användare som heter '{name}'.",
        # Password rules from core.auth.password_problem
        "password_too_short": "Lösenordet måste vara minst {min} tecken.",
        "password_too_long": "Lösenordet får vara högst {max} tecken.",
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
        "tab_receipt": "🛒 Current Receipt",
        "tab_history": "📜 History",
        # Login and registration
        "login_intro": "Log in to see your receipts, or create an account.",
        "login_tab": "🔐 Log in",
        "register_tab": "➕ Create account",
        "user_name_label": "User name",
        "password_label": "Password",
        "repeat_password_label": "Repeat the password",
        "log_in_button": "Log in",
        "create_account_button": "Create account",
        "login_failed": "Wrong user name or password.",
        "login_locked": "Too many failed attempts. Try again in {seconds} seconds.",
        "passwords_differ": "The passwords do not match.",
        "logged_in_as": "Logged in as **{name}**",
        "log_out_button": "🚪 Log out",
        "action_log_in": "log in",
        # Sidebar: users
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
        # Problems from core.receipt.validate_receipt
        "problem_item_missing": "Row {row}: the item description is missing.",
        "problem_item_too_long": "Row {row}: the item description is longer than {max} characters.",
        "problem_price_missing": "Row {row}: the price is missing.",
        "problem_price_out_of_range": "Row {row}: the price must be between -{max} and {max} kr.",
        # Rejected user names from db.create_user
        "user_name_empty": "User name cannot be empty.",
        "user_name_too_long": "User name can be at most {max} characters.",
        "user_name_taken": "A user named '{name}' already exists.",
        # Password rules from core.auth.password_problem
        "password_too_short": "The password must be at least {min} characters.",
        "password_too_long": "The password can be at most {max} characters.",
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

    Numbers in `params` are formatted for the language (format_number), so
    "{max}" becomes "100 000" in Swedish and "100,000" in English. An
    unsupported language falls back to DEFAULT_LANGUAGE. An unknown key or a
    missing parameter raises KeyError: a missing text is a bug, and the tests
    check that every key used exists in every language.
    """
    text = TRANSLATIONS[resolve_language(lang)][key]
    if not params:
        return text
    formatted = {
        name: format_number(value, lang) if _is_number(value) else value
        for name, value in params.items()
    }
    return text.format(**formatted)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_number(value, lang):
    """Format a number for the language: whole numbers without decimals, others with two.

    Swedish: "100 000" / "1 234,50". English: "100,000" / "1,234.50".
    """
    decimals = 0 if float(value).is_integer() else 2
    number = f"{value:,.{decimals}f}"
    if resolve_language(lang) == "sv":
        number = number.replace(",", _NBSP).replace(".", ",")
    return number


def category_label(name, lang):
    """How a stored category name is shown: FALLBACK_CATEGORY is translated, others as stored."""
    if name == FALLBACK_CATEGORY:
        return FALLBACK_CATEGORY_LABELS[resolve_language(lang)]
    return name


def category_value(label, lang):
    """The stored category name for a label shown in `lang` (reverse of category_label)."""
    if label == FALLBACK_CATEGORY_LABELS[resolve_language(lang)]:
        return FALLBACK_CATEGORY
    return label


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
