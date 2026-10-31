Project
ExpenseHandler: a Streamlit web application for tracking personal spending.
Users upload grocery receipts (ICA PDFs, to begin with), add manual purchases,
categorize items, and save them to a history so they can follow up on their expenses.

The app supports MULTIPLE USERS, and each user's data is COMPLETELY ISOLATED from every other user's.
"Isolated" means all data is user-specific: categories, which category an item belongs to (memory),
and history. No function may read or change another user's rows, and an action by one user
(e.g. deleting a category) never affects another user's data.
It does NOT mean authentication: there is no login, and anyone who opens the app can pick any user.
That is why the app only listens on localhost (see Security).

Code location
All code lives in this repository. The repository is public on GitHub (see Security).

Tech stack
- Python 3.12+
- Streamlit (web UI and state management)
- Pandas (data manipulation and tables)
- pypdf (PDF text extraction; replaces the unmaintained PyPDF2)
- SQLite3 (local persistent database)
- pytest (tests, dev only)
- Versions are pinned in `requirements.txt` / `requirements-dev.txt` (see Security).

Code conventions
- Language: code, variable names, comments, DataFrame columns, log messages and commits are in English.
  Everything the user sees is translated: it goes through `t(key, lang)` and exists in Swedish and
  English (see Languages). Never write user-facing text directly in `app.py`.
- Naming: `snake_case` for functions and variables.
- Modularization: each database operation (init, create, load, save, delete) is its own function.
- `core/` modules are pure functions: no Streamlit and no database imports. They take plain values
  (DataFrames, dicts, lists, bytes) and return them; callers pass in whatever they loaded from `db`.
- Shared values (`FALLBACK_CATEGORY`, `FALLBACK_CATEGORY_LABELS`, `RECEIPT_COLUMNS`, `MAX_NAME_LENGTH`,
  `MAX_ITEM_LENGTH`, `MAX_PRICE`) live only in `core/constants.py`. Never redefine them.
- Code below the UI (`core/`, `services/`, `integrations/`) returns translation keys, not sentences,
  for anything the user will read: `core.receipt.Problem(key, params)` and `db.UserNameError` (with
  `key` and `params`). The UI turns them into text with `t()`.
- Return named types, not bare tuples, when a result has several parts: `db.User(id, name)`,
  `core.parser.ParsedReceipt(items, purchase_date)`, `services.receipts.ImportResult(items,
  remembered, purchase_date)`. Use the field names (`user.name`), never positions (`user[1]`).
- "Draft" is the receipt being edited before it is saved: `st.session_state.receipt_df`, the local
  name `draft`, `set_draft` / `add_to_draft`, and `core/receipt.py` imported as `draft_ops` in `app.py`.
  "Receipt" alone means the purchase as a whole (the PDF, or what is saved to history).
- Write non-trivial regular expressions with `re.VERBOSE`, one commented line per part and an example
  line in the comment.

Architecture
- `app.py`: UI only (sidebar user handling, tabs, forms, tables, charts). It reads and writes
  `st.session_state` and calls `services/`, `core/` and `integrations/db.py`; business rules and
  multi-step flows do not belong here. Every `db` call goes through `load(...)` or `write_errors(...)`
  (see Error handling).
- `services/receipts.py`: flows that combine `core/` logic with the database, with no Streamlit:
  `import_receipt` (parse PDF, load memory, categorize -> `ImportResult`) and `save_receipt`
  (validate -> `InvalidReceipt(problems)`, or save history and memory in one transaction).
- `integrations/db.py`: all SQLite access, and the data rules that must always hold (see Database).
- `core/constants.py`: shared constants and input limits. Imports nothing, so every module may depend on it.
- `core/parser.py`: ICA PDF parsing.
- `core/receipt.py`: logic for the receipt being edited (normalize, add rows, apply `st.data_editor`
  changes, categorize from memory, validate before saving, decide what to remember on save).
- `core/calculator.py`: totals and per-category summaries.
- `core/text.py`: `escape_markdown` for showing user-provided text safely.
- `core/i18n.py`: translations (`TRANSLATIONS`, `t`), number and amount formatting per language,
  default categories per language and the fallback category label (see Languages).
- Dependency direction: `app.py` -> `services/`, `core/`, `integrations/`;
  `services/` -> `core/`, `integrations/`; `core/` -> `core/` only;
  `integrations/` -> `core/constants.py` only. `tests/test_architecture.py` enforces this.
- Connection handling: SQLite connections must use `check_same_thread=False`. Each `db` function opens
  and closes its own connection: writes use `with transaction() as conn:` (commit on success, rollback
  on error, always closed), reads use `closing(get_connection())`. All SQL uses `?` parameters; never
  build SQL with f-strings or `.format()`.
- State management: rely on `st.session_state` to prevent UI freezes and data loss on re-render.
  - `language`: "sv" or "en", bound to the language selector and mirrored in the URL as `?lang=`.
    Changing it keeps the user and the unsaved receipt.
  - `current_user`: id of the selected user. Nothing but the sidebar is shown until a user is selected.
    Switching user clears the unsaved receipt.
  - `receipt_df`: the receipt currently being edited (single source of truth for the table).
  - `table_version`: part of the `st.data_editor` key (together with the language). Edits are folded
    into `receipt_df` in the editor's `on_change`, then the version is bumped so the table is rebuilt
    and no edit is applied twice.
  - `upload_version`: part of the `st.file_uploader` key; bumped after a PDF is parsed so the same file
    is not parsed again on the next rerun.
  - `purchase_date`: the date that will be saved with the receipt (from the receipt, or picked by the user).
  - `date_version`: part of the date picker key; bumped when `purchase_date` is set from code
    (upload, save, clear, switch user) so the picker shows the new value.
  - `flash`: (kind, message) shown once after the next `st.rerun()`. It is rendered in a container that
    exists on every run, so the tabs below never move (moving them resets the selected tab).

Database (`expenses.db`)
Every table except `users` MUST be tied to a `user_id`, and every query on those tables MUST filter on it.
1. `users` (id, name) - name is unique.
2. `categories` (name, user_id) - unique on (name, user_id).
3. `memory` (item, category, user_id) - unique on (item, user_id); remembers the last category chosen for an item.
4. `history` (id, date, item, price, category, user_id) - date stored as `YYYY-MM-DD` text.
- `create_user(name, default_categories)` seeds the user's starting categories (the app passes
  `core.i18n.DEFAULT_CATEGORIES[language]`) and always adds `FALLBACK_CATEGORY`. Name errors are
  `UserNameEmpty`, `UserNameTooLong`, `UserNameTaken` (all `UserNameError`, a `ValueError`).
- `FALLBACK_CATEGORY` is stored as "Other" in every language and can never be deleted;
  `delete_category` refuses it. Its labels in every language ("Övrigt", "Other") are reserved:
  `add_category` rejects them in any letter case.
- Deleting a category also deletes that user's `memory` rows pointing at it, in the same transaction.
  `history` is never rewritten: saved purchases keep the category they were saved with.
- Input limits are enforced here as the last guard: `create_user` / `add_category` reject names longer
  than `MAX_NAME_LENGTH`; `save_history` rejects (and saves nothing) if an item is longer than
  `MAX_ITEM_LENGTH` or a price is outside -`MAX_PRICE`..`MAX_PRICE`.
- Only the user's own categories are accepted: `save_history` stores any other category as
  `FALLBACK_CATEGORY`, and `save_memory` skips it. Another user's category can never be used.
- A flow that writes more than once must do so in ONE transaction, so a failure leaves nothing
  half-saved and a retry cannot duplicate rows. `save_receipt(user_id, purchase_date, items_df, memory)`
  writes history and memory together; the private `_write_history` / `_write_memory` helpers take an
  open connection so they can be combined. The memory mapping is passed in because `integrations/`
  may not import `core/receipt.py`.
- Always use `CREATE TABLE IF NOT EXISTS`. Keep the schema stable.
- The `EXPENSES_DB_PATH` environment variable points the app at another database file
  (used for manual testing; the test suite patches `db.DB_PATH` instead).
- The legacy `kvitto_minne.db` (tables `minne`, `kategorier`, `historik`) belongs to the old receipt-splitter version and is not used.

PDF parsing
- `read_receipt(file_bytes)` reads the upload via `io.BytesIO` and pypdf and returns
  `ParsedReceipt(items, purchase_date)` - a DataFrame with `Item` and `Price`, and the date printed on
  the receipt (`None` if not found). The app calls it through `services.receipts.import_receipt`.
- Bytes that do not start with `%PDF-` raise `NotAPdfError` before pypdf sees them. Any error raised by
  pypdf itself becomes `ReceiptReadError` (the pypdf exception is kept as `__cause__`).
- Designed specifically for the ICA receipt format: process line by line, pick up item lines ending in
  `st` or `kg`, parse the price, and capture discounts (negative amounts), which are merged into the
  item above. Back-to-back lines with the same article number are combined into one row.
  Parsing stops at the payment section (`Delavstämning`, `Betalat`, `Betalningsinformation`).
- The purchase date is the first valid `YYYY-MM-DD` in the text; text extraction may glue it to a label
  (e.g. `Kassör2026-09-26`).

UI
- Sidebar: language selector (Svenska / English) at the top, then a dropdown to select an existing
  user and a text field to create a new one.
- Tab "🛒 Current Receipt" ("🛒 Aktuellt kvitto"): add/remove categories, manual entry (item, price, category), PDF upload
  (categories pre-filled from the user's memory, purchase date from the receipt), `st.data_editor`
  for the current list, date picker + save button that writes to `history` and learns category
  choices into `memory`. Save is blocked with the per-row list of problems from `InvalidReceipt`.
- Tab "📜 History" ("📜 Historik"): pick a start and end date, show total spent, an `st.bar_chart` per category,
  the list of purchases, and delete all purchases saved on a date (with confirmation).

Languages
- Supported: Swedish (`sv`, the default) and English (`en`), listed in `core.i18n.LANGUAGES`.
- Where the language is kept: `st.session_state.language` and the URL (`?lang=sv`). On the first run
  in a browser tab it is read from `?lang=` (unknown values fall back to Swedish); after that the
  selector writes it back to the URL, so a reload or bookmark keeps it. It is NOT stored per user:
  a new tab without `?lang=` starts in Swedish, and switching user keeps the tab's language.
- Adding or changing a text: add the same key to every language in `core.i18n.TRANSLATIONS`, with the
  same `{placeholders}`, and use it with `t("key", lang())`. `tests/test_i18n.py` fails if a key is
  missing in a language, has different placeholders, or is defined but never used.
- `t()` formats numeric parameters for the language (`format_number`): "100 000" in Swedish,
  "100,000" in English. Amounts in kronor use `format_amount`: "1 122,17 kr" / "1,122.17 kr".
  Dates are shown as `YYYY-MM-DD` in both languages.
- `load(..., what="what_...")` and `write_errors("action_...")` take translation keys; their log lines
  use the English text (logs stay in English).
- Categories: a new user's starting categories are created in the language selected at that moment
  (`DEFAULT_CATEGORIES`) and are the user's own data from then on; they are never translated. Only
  `FALLBACK_CATEGORY` is translated: stored as "Other", shown via `category_label` ("Övrigt" in
  Swedish). The receipt editor shows a copy with labels (`with_category_labels`) and maps edits back
  to stored names (`changes_to_stored_categories`); select boxes list labels and map the choice back
  with `category_value`. Never store a label.

Error handling
- Catch errors from external code at the boundary where it is called, and turn them into our own
  types or messages: pypdf -> `ReceiptReadError` (in `core/parser.extract_text`), SQLite ->
  `sqlite3.Error` handled in `app.py`. Only external calls go inside these `try` blocks.
- Never wrap our own code in `except Exception`. A bug must surface: Streamlit logs the full traceback
  and shows a generic message. `except Exception` is allowed only at the pypdf boundary, and
  `tests/test_parser.py` checks that it appears nowhere else.
- Database reads in `app.py` use `load(fetch, *args, what=...)`: on `sqlite3.Error` it logs, shows
  "Could not load ..." with a "Try again" button and raises `DataUnavailable`, which `render_section`
  catches so only that part of the page stops (the user list and selected user stop the whole page).
- Database writes in `app.py` run inside `with write_errors("<action>"):`, together with everything
  that should only happen on success (reset, flash, `st.rerun()`). On `sqlite3.Error` it logs and shows
  "Could not <action> ... try again"; the user's input stays on the page.
- Log with `logging` (`logger.exception` / `logger.warning(..., exc_info=True)`). Log messages must not
  contain receipt data, item names or other personal data.
- Expected problems with user input are not exceptions to log: show them directly (validation
  problems from `InvalidReceipt`, `NotAPdfError`, duplicate user name).

Security
- Network: `.streamlit/config.toml` sets `server.address = "localhost"`. The app has no login, so it
  must never listen on other interfaces. Do not remove this or start the app with `--server.address`.
  The config file is only read when the app is started from the repository root.
- Error details: `client.showErrorDetails = "none"`. Never show exception or library error text to the
  user; show a short generic message instead (see the PDF upload handler).
- Uploads: `server.maxUploadSize = 5` (MB); uploads must start with `%PDF-` and are parsed with pypdf.
  Never go back to PyPDF2 (unmaintained, unpatched denial-of-service bugs such as CVE-2023-36464).
- User-provided text (user, category and item names) is rendered by Markdown elements (`st.caption`,
  `st.success`, `st.error`, ...). Always pass it through `escape_markdown` first; otherwise a name can
  load remote images or create links. Plain-text widgets (selectbox options, tables, chart labels)
  do not need it.
- Input limits (`core/constants.py`): names 1-`MAX_NAME_LENGTH` (50) characters, items up to
  `MAX_ITEM_LENGTH` (100) characters, prices within -`MAX_PRICE`..`MAX_PRICE` (100 000 kr). Enforce them
  in the UI (`max_chars`, `min_value`/`max_value`), in `validate_receipt` before saving, and in `db.py`.
- Dependencies are pinned with `~=X.Y.Z` (patch releases only). Raise a pin deliberately, run the tests,
  and check release notes for security fixes when doing so; minor releases are not picked up automatically.
- The repository is public. Never commit real receipts, databases, personal paths (e.g. a user's home or
  OneDrive folder) or personal e-mail addresses. Commits use the GitHub noreply address.
  `tests/test_no_personal_data.py` fails if tracked files contain such paths or e-mail addresses.
- `expenses.db` is stored unencrypted next to the code and is ignored by git.

Rules
- Do not break Streamlit's reactive loop. Use `st.form` for input and `st.session_state` for anything
  that triggers heavy updates.
- All file operations on uploaded PDFs must use `io.BytesIO`.
- Never read or write another user's rows: every function in `db.py` except the `users` functions takes `user_id`.
- New logic goes in `core/` with tests; flows that also need the database go in `services/`;
  `app.py` only wires them to the UI.
- Follow the Security section for anything that renders user text, accepts input or adds a dependency,
  and the Error handling section for anything that calls the database or an external library.

Testing
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Run: `python -m pytest`
- `tests/test_db.py`: data layer, including user isolation, input limits, transactions and atomic
  `save_receipt`. Each test uses its own temporary database.
- `tests/test_parser.py`, `tests/test_receipt.py`, `tests/test_calculator.py`, `tests/test_text.py`:
  pure `core/` logic.
- `tests/test_services.py`: `services/receipts.py` flows against a temporary database.
- `tests/test_app.py`: headless UI tests with Streamlit's `AppTest` (including that user text is shown
  literally). PDF upload and `st.data_editor` interactions are not supported by `AppTest`; check those
  in a browser.
- `tests/test_app_db_errors.py`: the UI with simulated database errors (messages, "Try again", input
  kept, retry saves once, no receipt data in logs).
- `tests/test_architecture.py`: the dependency direction between layers.
- `tests/test_i18n.py`: translation tables (same keys and placeholders in every language, every used
  key exists, no unused keys), number/amount formatting and category labels.
- `tests/test_app_language.py`: the UI in both languages (`?lang=`, switching, kept state, translated
  messages and categories). Other UI tests run in English via `start_app(lang="en")`.
- `tests/test_streamlit_config.py`, `tests/test_requirements.py`, `tests/test_no_personal_data.py`:
  keep the security settings, version pins and the absence of personal data in place.
- Optional real-receipt test: set `ICA_SAMPLE_PDF` to a local receipt (and `ICA_SAMPLE_TOTAL` to its
  "Betalat" amount, e.g. `1122.17`) to run it; it is skipped otherwise.

Known limitations
- No authentication (see Project); the app is protected only by listening on localhost.
- `expenses.db` is not encrypted.
- `st.tabs` runs both tabs on every rerun, so the History query also runs while editing a receipt.
  Accepted for now.
- The language is remembered per browser tab/URL, not per user.
- Prices in number inputs and tables (`PRICE_INPUT_FORMAT`) always use a decimal point ("1122.17"):
  these Streamlit widgets only accept printf-style formats. Totals and messages are localized.
- Streamlit's own widget texts ("Press Enter to submit form", "Upload", "… per file") are English and
  cannot be translated. The date picker's month names follow the browser's language.
- Switching language changes the tab labels, so Streamlit shows the first tab again (checked in the
  browser: switching while on History opens "Current Receipt").

Project structure
/
├── app.py
├── .streamlit/
│   └── config.toml     # Security settings (localhost only, upload size, error details)
├── services/
│   └── receipts.py     # Import and save flows (core + database, no Streamlit)
├── integrations/
│   └── db.py
├── core/
│   ├── constants.py
│   ├── parser.py
│   ├── receipt.py
│   ├── calculator.py
│   ├── i18n.py         # Translations, number formatting, categories per language
│   └── text.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_app_db_errors.py
│   ├── test_app_language.py
│   ├── test_architecture.py
│   ├── test_calculator.py
│   ├── test_db.py
│   ├── test_i18n.py
│   ├── test_no_personal_data.py
│   ├── test_parser.py
│   ├── test_receipt.py
│   ├── test_requirements.py
│   ├── test_services.py
│   ├── test_streamlit_config.py
│   └── test_text.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── expenses.db         # Auto-generated on first run (not committed)

Commits
- Commit messages are in English: a short summary line, a blank line, then what changed and why.
- Work done as a numbered plan uses a prefix with the plan's name and step number, e.g.
  `Code Quality Step 3: handle database errors in the UI with retry`, `Security step 2: ...` or
  `Language Step 5: ...`.
- One commit per step; push only when the user asks.

Setup
pip install -r requirements.txt

Run (from the repository root, so .streamlit/config.toml is used)
python -m streamlit run app.py
