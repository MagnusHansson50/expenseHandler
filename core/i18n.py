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
        "desktop_running": (
            "ExpenseHandler körs på {url} och öppnas i webbläsaren. Dina kvitton sparas i {path}. "
            "Stäng det här fönstret för att avsluta."
        ),
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
        "delete_account_header": "🗑️ Ta bort mitt konto",
        "delete_account_warning": "Kontot, dina kategorier och hela din historik raderas för gott. Det går inte att ångra.",
        "delete_confirm_label": "Jag förstår att allt raderas",
        "delete_account_button": "Ta bort kontot",
        "delete_confirm_required": "Kryssa i rutan för att bekräfta att allt ska raderas.",
        "delete_wrong_password": "Fel lösenord. Kontot har inte tagits bort.",
        "account_deleted": "Ditt konto och alla dina kvitton är borttagna.",
        "action_delete_account": "ta bort kontot",
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
        "add_missing_item": "➕ Lägg till en vara som saknas",
        "add_to_list": "➕ Lägg till i listan",
        "item_missing": "Ange en beskrivning av varan.",
        "upload_label": "Ladda upp ett kvitto från Kivra eller Willys (.pdf)",
        "not_a_pdf": "Filen är ingen PDF. Ladda ner kvittot som PDF från Kivra eller Willys och ladda upp den.",
        "pdf_unreadable": "Det gick inte att läsa PDF-filen. Kontrollera att det är ett kvitto från Kivra eller Willys och försök igen.",
        "unknown_receipt_format": "Kvittoformatet känns inte igen. Bara kvitton från Kivra och Willys kan läsas in; lägg in andra köp manuellt.",
        "no_items_found": "Inga varor hittades i PDF-filen.",
        "review_open_button": "🏷️ Gå igenom varor utan kategori ({count})",
        "review_title": "🏷️ Varor utan kategori",
        "review_position": "Vara {position} av {total}",
        "review_choose_label": "Välj kategori – ett klick sparar och går vidare till nästa vara",
        "review_remove_header": "🗑️ Ta bort en kategori",
        "remove_category_note": "Kategorin tas bort ur dina kategorier och ur minnet. Köp du redan har sparat behåller den. Varor i det osparade kvittot som har den hamnar i Övrigt.",
        "remove_category_confirm": "Ja, ta bort kategorin",
        "review_skip_button": "Hoppa över",
        "review_stop_button": "Avsluta",
        "review_done": "Alla varor har nu en kategori. Valen sparas i minnet när du sparar kvittot.",
        "review_done_skipped": "Genomgången är klar. Varor som du hoppade över och som fortfarande saknar kategori: {count}.",
        "import_added": "{count} varor har lagts till ({remembered} fick kategori från minnet).",
        "import_date_set": "Köpdatumet är satt till {date} från kvittot.",
        "import_no_date": "Inget datum hittades på kvittot; kontrollera köpdatumet.",
        "paid_items_missing": (
            "Kvittot anger Betalat {paid_total}, men listan är {difference} mindre. Saknas en vara, "
            "lägg till den under Lägg till en vara som saknas, eller rätta ett pris i tabellen."
        ),
        "paid_items_too_much": (
            "Kvittot anger Betalat {paid_total}, men listan är {difference} mer. Ta bort det som inte "
            "ska vara med under Ta bort en vara, eller rätta ett pris i tabellen."
        ),
        "paid_matches": "✔️ Listan stämmer med kvittots Betalat {paid_total}.",
        # Draft receipt table and saving
        "empty_draft_info": "Lägg till ett köp manuellt eller ladda upp ett kvitto för att komma igång.",
        "current_list": "Aktuell lista",
        "receipt_table_hint": "Du kan ändra vara, pris och kategori direkt i tabellen. Saknas en vara, lägg till den i tabellens tomma rad längst ner eller under Lägg till en vara som saknas.",
        "remove_item_header": "🗑️ Ta bort en vara",
        "remove_item_note": "Till exempel något du köpte åt någon annan. Varan tas bara bort ur det här kvittot; den sparas inte och appen lägger den inte på minnet.",
        "remove_item_choice": "Vara att ta bort",
        "remove_item_option": "Rad {row}: {item} – {amount}",
        "col_item": "Vara",
        "col_price": "Pris (kr)",
        "col_category": "Kategori",
        "chart_amount": "Summa (kr)",
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
        "backup_too_large": "Filen är större än {max} MB och kan inte vara en säkerhetskopia från ExpenseHandler.",
        "backup_unreadable": "Filen är ingen säkerhetskopia från ExpenseHandler, eller så är den skadad.",
        "backup_too_new": "Säkerhetskopian kommer från en nyare version av ExpenseHandler (format {version}, den här versionen klarar {supported}). Installera den senaste versionen.",
        "backup_bad_category": "Kategorin \"{name}\" är tom, för lång eller ett reserverat namn.",
        "backup_bad_memory": "Det sparade kategorivalet för \"{item}\" är ogiltigt.",
        "backup_bad_entry": "Rad {row}: köpet saknar datum, vara, pris eller kategori, eller har fel typ av värde.",
        "backup_bad_date": "Rad {row}: datumet är inte ett giltigt datum (ÅÅÅÅ-MM-DD).",
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
        "change_category_hint": "Fel kategori? Klicka på kategorin, välj en annan och klicka på Spara ändringar. Appen kommer ihåg den till nästa gång.",
        "save_category_changes": "💾 Spara ändringar",
        "categories_changed": "{count} köp fick en ny kategori.",
        "no_category_changes": "Ingen kategori ändrades.",
        "delete_receipt_expander": "🗑️ Radera ett sparat kvitto",
        "confirm_delete": "Ja, radera alla köp som sparats detta datum",
        "delete_button": "Radera",
        "tick_to_confirm": "Kryssa i rutan för att bekräfta.",
        "deleted_rows": "{count} rader raderades från {date}.",
        # Database errors: "Kunde inte läsa in <what>" / "Kunde inte <action>"
        "load_failed": "Kunde inte läsa in {what}. Databasen kan vara upptagen.",
        "try_again": "🔄 Försök igen",
        "write_failed": "Kunde inte {action}. Databasen kan vara upptagen – försök igen.",
        "database_too_new": (
            "Databasen har skapats av en nyare version av ExpenseHandler (databasversion {found}, "
            "den här versionen klarar {supported}). Installera den senaste versionen. Inget har ändrats i dina data."
        ),
        "what_database": "databasen",
        "what_selected_user": "den valda användaren",
        "what_categories": "dina kategorier",
        "what_memory": "dina sparade kategorival",
        "what_saved_dates": "dina sparade datum",
        "what_history": "din historik",
        "backup_header": "💾 Säkerhetskopia",
        "backup_intro": "Ladda ner en säkerhetskopia av dina kategorier, kategorival och hela historiken, till exempel inför byte av dator, och läs in den igen i ett konto. Filen är inte krypterad och innehåller alla dina köp: förvara den säkert. Lösenordet följer inte med.",
        "backup_download_button": "⬇️ Ladda ner säkerhetskopia",
        "backup_csv_button": "⬇️ Ladda ner historiken som CSV (Excel)",
        "backup_upload_label": "Läs in en säkerhetskopia (.json)",
        "backup_imported": "Säkerhetskopian är inläst. Tillagda köp: {purchases}, kategorier: {categories}, kategorival: {memory}.",
        "backup_nothing_new": "Säkerhetskopian är inläst. Allt i den fanns redan, så inget lades till.",
        "backup_not_imported": "Säkerhetskopian lästes inte in, inget har ändrats:",
        "backup_more_problems": "… och {count} problem till.",
        "action_import_backup": "läsa in säkerhetskopian",
        "what_backup": "säkerhetskopian",
        "action_create_user": "skapa användaren",
        "action_add_category": "lägga till kategorin",
        "action_remove_category": "ta bort kategorin",
        "action_save_receipt": "spara kvittot",
        "action_delete_receipt": "radera kvittot",
        "action_change_categories": "spara de ändrade kategorierna",
    },
    "en": {
        # Page and navigation
        "app_title": "🧾 ExpenseHandler",
        "desktop_running": (
            "ExpenseHandler is running at {url} and opens in your browser. Your receipts are saved in {path}. "
            "Close this window to quit."
        ),
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
        "delete_account_header": "🗑️ Delete my account",
        "delete_account_warning": "The account, your categories and your whole history are deleted for good. This cannot be undone.",
        "delete_confirm_label": "I understand that everything is deleted",
        "delete_account_button": "Delete the account",
        "delete_confirm_required": "Tick the box to confirm that everything should be deleted.",
        "delete_wrong_password": "Wrong password. The account was not deleted.",
        "account_deleted": "Your account and all your receipts have been deleted.",
        "action_delete_account": "delete the account",
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
        "add_missing_item": "➕ Add a missing item",
        "add_to_list": "➕ Add to list",
        "item_missing": "Enter an item description.",
        "upload_label": "Upload a receipt from Kivra or Willys (.pdf)",
        "not_a_pdf": "The file is not a PDF. Download the receipt as a PDF from Kivra or Willys and upload it.",
        "pdf_unreadable": "Could not read the PDF. Check that it is a receipt from Kivra or Willys and try again.",
        "unknown_receipt_format": "The receipt layout is not recognized. Only receipts from Kivra and Willys can be imported; add other purchases manually.",
        "no_items_found": "No items were found in the PDF.",
        "review_open_button": "🏷️ Go through items without a category ({count})",
        "review_title": "🏷️ Items without a category",
        "review_position": "Item {position} of {total}",
        "review_choose_label": "Choose a category – one click saves it and moves to the next item",
        "review_remove_header": "🗑️ Remove a category",
        "remove_category_note": "The category is removed from your categories and from what is remembered. Purchases you have already saved keep it. Items on the unsaved receipt that have it move to Other.",
        "remove_category_confirm": "Yes, remove the category",
        "review_skip_button": "Skip",
        "review_stop_button": "Stop",
        "review_done": "Every item now has a category. The choices are remembered when you save the receipt.",
        "review_done_skipped": "The review is done. Items you skipped that still have no category: {count}.",
        "import_added": "Added {count} items ({remembered} categorized from memory).",
        "import_date_set": "Purchase date set to {date} from the receipt.",
        "import_no_date": "No date found on the receipt; check the purchase date.",
        "paid_items_missing": (
            "The receipt says Betalat (paid) {paid_total}, but the list is {difference} less. If an "
            "item is missing, add it under Add a missing item, or correct a price in the table."
        ),
        "paid_items_too_much": (
            "The receipt says Betalat (paid) {paid_total}, but the list is {difference} more. Remove "
            "what should not be included under Remove an item, or correct a price in the table."
        ),
        "paid_matches": "✔️ The list matches the receipt's Betalat (paid) {paid_total}.",
        # Draft receipt table and saving
        "empty_draft_info": "Add a purchase manually or upload a receipt to get started.",
        "current_list": "Current list",
        "receipt_table_hint": "You can change the item, price and category right in the table. If an item is missing, add it in the table's empty row at the bottom or under Add a missing item.",
        "remove_item_header": "🗑️ Remove an item",
        "remove_item_note": "For example something you bought for someone else. The item is only removed from this receipt; it is not saved and the app does not remember it.",
        "remove_item_choice": "Item to remove",
        "remove_item_option": "Row {row}: {item} – {amount}",
        "col_item": "Item",
        "col_price": "Price (kr)",
        "col_category": "Category",
        "chart_amount": "Total (kr)",
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
        "backup_too_large": "The file is larger than {max} MB and cannot be an ExpenseHandler backup.",
        "backup_unreadable": "The file is not an ExpenseHandler backup, or it is damaged.",
        "backup_too_new": "The backup comes from a newer version of ExpenseHandler (format {version}, this version supports {supported}). Install the latest version.",
        "backup_bad_category": "The category \"{name}\" is empty, too long or a reserved name.",
        "backup_bad_memory": "The remembered category for \"{item}\" is not valid.",
        "backup_bad_entry": "Row {row}: the purchase lacks a date, item, price or category, or has the wrong kind of value.",
        "backup_bad_date": "Row {row}: the date is not a valid date (YYYY-MM-DD).",
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
        "change_category_hint": "Wrong category? Click the category, pick another and click Save changes. The app remembers it for next time.",
        "save_category_changes": "💾 Save changes",
        "categories_changed": "{count} purchases got a new category.",
        "no_category_changes": "No category was changed.",
        "delete_receipt_expander": "🗑️ Delete a saved receipt",
        "confirm_delete": "Yes, delete every purchase saved on this date",
        "delete_button": "Delete",
        "tick_to_confirm": "Tick the box to confirm.",
        "deleted_rows": "Deleted {count} rows from {date}.",
        # Database errors: "Could not load <what>" / "Could not <action>"
        "load_failed": "Could not load {what}. The database may be busy.",
        "try_again": "🔄 Try again",
        "write_failed": "Could not {action}. The database may be busy; please try again.",
        "database_too_new": (
            "The database was created by a newer version of ExpenseHandler (database version {found}, "
            "this version supports {supported}). Install the latest version. Nothing in your data was changed."
        ),
        "what_database": "the database",
        "what_selected_user": "the selected user",
        "what_categories": "your categories",
        "what_memory": "your remembered categories",
        "what_saved_dates": "your saved dates",
        "what_history": "your history",
        "backup_header": "💾 Backup",
        "backup_intro": "Download a backup of your categories, remembered choices and whole history, for example before moving to another computer, and read it back into an account. The file is not encrypted and contains all your purchases: keep it safe. Your password is not included.",
        "backup_download_button": "⬇️ Download backup",
        "backup_csv_button": "⬇️ Download history as CSV (Excel)",
        "backup_upload_label": "Read in a backup (.json)",
        "backup_imported": "The backup was read in. Added purchases: {purchases}, categories: {categories}, remembered choices: {memory}.",
        "backup_nothing_new": "The backup was read in. Everything in it was already there, so nothing was added.",
        "backup_not_imported": "The backup was not read in; nothing was changed:",
        "backup_more_problems": "… and {count} more problems.",
        "action_import_backup": "read in the backup",
        "what_backup": "the backup",
        "action_create_user": "create the user",
        "action_add_category": "add the category",
        "action_remove_category": "remove the category",
        "action_save_receipt": "save the receipt",
        "action_delete_receipt": "delete the receipt",
        "action_change_categories": "save the changed categories",
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
