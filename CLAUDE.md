Project
ExpenseHandler: a Streamlit web application for tracking personal spending.
Users upload grocery receipts (ICA PDFs, to begin with), add manual purchases,
categorize items, and save them to a history so they can follow up on their expenses.

The app supports MULTIPLE USERS, and each user's data is COMPLETELY ISOLATED from every other user's.
"Isolated" means all data is user-specific: categories, which category an item belongs to (memory),
and history. No function may read or change another user's rows, and an action by one user
(e.g. deleting a category) never affects another user's data.
It does NOT mean authentication: there is no login, and anyone who opens the app can pick any user.

Code location
All code lives in this repository.

Tech stack
- Python 3.12+
- Streamlit (web UI and state management)
- Pandas (data manipulation and tables)
- PyPDF2 (PDF text extraction)
- SQLite3 (local persistent database)
- pytest (tests, dev only)

Code conventions
- Language: UI text, variable names, comments and DataFrame columns in English.
- Naming: `snake_case` for functions and variables.
- Modularization: each database operation (init, create, load, save, delete) is its own function.
- `core/` modules are pure functions: no Streamlit and no database imports. They take plain values
  (DataFrames, dicts, lists, bytes) and return them; the UI passes in whatever it has loaded from `db`.
- Shared values (`FALLBACK_CATEGORY`, `RECEIPT_COLUMNS`) live only in `core/constants.py`. Never redefine them.

Architecture
- `app.py`: UI only (sidebar user handling, tabs, forms, tables, charts). It reads and writes
  `st.session_state` and calls `core/` and `integrations/db.py`; business rules do not belong here.
- `integrations/db.py`: all SQLite access, and the data rules that must always hold (see Database).
- `core/constants.py`: shared constants. Imports nothing, so every module may depend on it.
- `core/parser.py`: ICA PDF parsing.
- `core/receipt.py`: logic for the receipt being edited (normalize, add rows, apply `st.data_editor`
  changes, categorize from memory, decide what to remember on save).
- `core/calculator.py`: totals and per-category summaries.
- Dependency direction: `app.py` -> `core/`, `integrations/`; `integrations/` -> `core/constants.py` only.
- Connection handling: SQLite connections must use `check_same_thread=False`. Each `db` function opens
  and closes its own connection.
- State management: rely on `st.session_state` to prevent UI freezes and data loss on re-render.
  - `current_user`: id of the selected user. Nothing but the sidebar is shown until a user is selected.
    Switching user clears the unsaved receipt.
  - `receipt_df`: the receipt currently being edited (single source of truth for the table).
  - `table_version`: part of the `st.data_editor` key. Edits are folded into `receipt_df` in the editor's
    `on_change`, then the version is bumped so the table is rebuilt and no edit is applied twice.
  - `upload_version`: part of the `st.file_uploader` key; bumped after a PDF is parsed so the same file
    is not parsed again on the next rerun.
  - `purchase_date`: the date that will be saved with the receipt (from the receipt, or picked by the user).
  - `date_version`: part of the date picker key; bumped when `purchase_date` is set from code
    (upload, save, clear, switch user) so the picker shows the new value.
  - `flash`: (kind, message) shown once after the next `st.rerun()`.

Database (`expenses.db`)
Every table except `users` MUST be tied to a `user_id`, and every query on those tables MUST filter on it.
1. `users` (id, name) - name is unique.
2. `categories` (name, user_id) - unique on (name, user_id).
3. `memory` (item, category, user_id) - unique on (item, user_id); remembers the last category chosen for an item.
4. `history` (id, date, item, price, category, user_id) - date stored as `YYYY-MM-DD` text.
- Creating a user automatically seeds a default set of categories (Dairy, Pantry, Fruit, Vegetables, Other, ...).
- `FALLBACK_CATEGORY` ("Other") can never be deleted; `delete_category` refuses it.
- Deleting a category also deletes that user's `memory` rows pointing at it, in the same transaction.
  `history` is never rewritten: saved purchases keep the category they were saved with.
- Always use `CREATE TABLE IF NOT EXISTS`. Keep the schema stable.
- The `EXPENSES_DB_PATH` environment variable points the app at another database file
  (used for manual testing; the test suite patches `db.DB_PATH` instead).
- The legacy `kvitto_minne.db` (tables `minne`, `kategorier`, `historik`) belongs to the old receipt-splitter version and is not used.

PDF parsing
- `read_receipt(file_bytes)` is what the app uses: it reads the upload via `io.BytesIO` and PyPDF2 and
  returns `(items, purchase_date)` - a DataFrame with `Item` and `Price`, and the date printed on the
  receipt (`None` if not found).
- `parse_pdf(file_bytes)` returns only the items DataFrame.
- Designed specifically for the ICA receipt format: process line by line, pick up item lines ending in
  `st` or `kg`, parse the price, and capture discounts (negative amounts), which are merged into the
  item above. Back-to-back lines with the same article number are combined into one row.
  Parsing stops at the payment section (`Delavstämning`, `Betalat`, `Betalningsinformation`).
- The purchase date is the first valid `YYYY-MM-DD` in the text; PyPDF2 may glue it to a label
  (e.g. `Kassör2026-09-26`).

UI
- Sidebar: dropdown to select an existing user, text field to create a new one.
- Tab "🛒 Current Receipt": add/remove categories, manual entry (item, price, category), PDF upload
  (categories pre-filled from the user's memory, purchase date from the receipt), `st.data_editor`
  for the current list, date picker + save button that writes to `history` and learns category
  choices into `memory`.
- Tab "📜 History": pick a start and end date, show total spent, an `st.bar_chart` per category,
  the list of purchases, and delete all purchases saved on a date (with confirmation).

Rules
- Do not break Streamlit's reactive loop. Use `st.form` for input and `st.session_state` for anything
  that triggers heavy updates.
- All file operations on uploaded PDFs must use `io.BytesIO`.
- Never read or write another user's rows: every function in `db.py` except the `users` functions takes `user_id`.
- New logic goes in `core/` with tests; `app.py` only wires it to the UI.
- Never commit real receipts (they contain personal and payment data).

Testing
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Run: `python -m pytest`
- `tests/test_db.py`: data layer, including user isolation. Each test uses its own temporary database.
- `tests/test_parser.py`, `tests/test_receipt.py`, `tests/test_calculator.py`: pure `core/` logic.
- `tests/test_app.py`: headless UI tests with Streamlit's `AppTest`. PDF upload and `st.data_editor`
  interactions are not supported by `AppTest`; check those in a browser.
- Optional real-receipt test: set `ICA_SAMPLE_PDF` to a local receipt (and `ICA_SAMPLE_TOTAL` to its
  "Betalat" amount, e.g. `1122.17`) to run it; it is skipped otherwise.

Known limitations
- No authentication (see Project).
- `st.tabs` runs both tabs on every rerun, so the History query also runs while editing a receipt.
  Accepted for now.
- PyPDF2 is deprecated in favour of `pypdf`; switching is a separate task.

Project structure
/
├── app.py
├── integrations/
│   └── db.py
├── core/
│   ├── constants.py
│   ├── parser.py
│   ├── receipt.py
│   └── calculator.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_calculator.py
│   ├── test_db.py
│   ├── test_parser.py
│   └── test_receipt.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── expenses.db         # Auto-generated on first run (not committed)

Setup
pip install -r requirements.txt
# Alternatively: pip install streamlit pandas PyPDF2

Run
python -m streamlit run app.py
