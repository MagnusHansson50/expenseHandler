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
- Language: UI text, variable names, comments and DataFrame columns in English.
- Naming: `snake_case` for functions and variables.
- Modularization: each database operation (init, create, load, save, delete) is its own function.
- `core/` modules are pure functions: no Streamlit and no database imports. They take plain values
  (DataFrames, dicts, lists, bytes) and return them; the UI passes in whatever it has loaded from `db`.
- Shared values (`FALLBACK_CATEGORY`, `RECEIPT_COLUMNS`, `MAX_NAME_LENGTH`, `MAX_ITEM_LENGTH`,
  `MAX_PRICE`) live only in `core/constants.py`. Never redefine them.

Architecture
- `app.py`: UI only (sidebar user handling, tabs, forms, tables, charts). It reads and writes
  `st.session_state` and calls `core/` and `integrations/db.py`; business rules do not belong here.
- `integrations/db.py`: all SQLite access, and the data rules that must always hold (see Database).
- `core/constants.py`: shared constants and input limits. Imports nothing, so every module may depend on it.
- `core/parser.py`: ICA PDF parsing.
- `core/receipt.py`: logic for the receipt being edited (normalize, add rows, apply `st.data_editor`
  changes, categorize from memory, validate before saving, decide what to remember on save).
- `core/calculator.py`: totals and per-category summaries.
- `core/text.py`: `escape_markdown` for showing user-provided text safely.
- Dependency direction: `app.py` -> `core/`, `integrations/`; `integrations/` -> `core/constants.py` only.
- Connection handling: SQLite connections must use `check_same_thread=False`. Each `db` function opens
  and closes its own connection. All SQL uses `?` parameters; never build SQL with f-strings or `.format()`.
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
  - `flash`: (kind, message) shown once after the next `st.rerun()`. It is rendered in a container that
    exists on every run, so the tabs below never move (moving them resets the selected tab).

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
- Input limits are enforced here as the last guard: `create_user` / `add_category` reject names longer
  than `MAX_NAME_LENGTH`; `save_history` rejects (and saves nothing) if an item is longer than
  `MAX_ITEM_LENGTH` or a price is outside -`MAX_PRICE`..`MAX_PRICE`.
- Only the user's own categories are accepted: `save_history` stores any other category as
  `FALLBACK_CATEGORY`, and `save_memory` skips it. Another user's category can never be used.
- Always use `CREATE TABLE IF NOT EXISTS`. Keep the schema stable.
- The `EXPENSES_DB_PATH` environment variable points the app at another database file
  (used for manual testing; the test suite patches `db.DB_PATH` instead).
- The legacy `kvitto_minne.db` (tables `minne`, `kategorier`, `historik`) belongs to the old receipt-splitter version and is not used.

PDF parsing
- `read_receipt(file_bytes)` is what the app uses: it reads the upload via `io.BytesIO` and pypdf and
  returns `(items, purchase_date)` - a DataFrame with `Item` and `Price`, and the date printed on the
  receipt (`None` if not found).
- Bytes that do not start with `%PDF-` raise `NotAPdfError` before pypdf sees them.
- `parse_pdf(file_bytes)` returns only the items DataFrame.
- Designed specifically for the ICA receipt format: process line by line, pick up item lines ending in
  `st` or `kg`, parse the price, and capture discounts (negative amounts), which are merged into the
  item above. Back-to-back lines with the same article number are combined into one row.
  Parsing stops at the payment section (`Delavstämning`, `Betalat`, `Betalningsinformation`).
- The purchase date is the first valid `YYYY-MM-DD` in the text; text extraction may glue it to a label
  (e.g. `Kassör2026-09-26`).

UI
- Sidebar: dropdown to select an existing user, text field to create a new one.
- Tab "🛒 Current Receipt": add/remove categories, manual entry (item, price, category), PDF upload
  (categories pre-filled from the user's memory, purchase date from the receipt), `st.data_editor`
  for the current list, date picker + save button that writes to `history` and learns category
  choices into `memory`. Save is blocked with a per-row list of problems from `validate_receipt`.
- Tab "📜 History": pick a start and end date, show total spent, an `st.bar_chart` per category,
  the list of purchases, and delete all purchases saved on a date (with confirmation).

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
- New logic goes in `core/` with tests; `app.py` only wires it to the UI.
- Follow the Security section for anything that renders user text, accepts input or adds a dependency.

Testing
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Run: `python -m pytest`
- `tests/test_db.py`: data layer, including user isolation and input limits. Each test uses its own
  temporary database.
- `tests/test_parser.py`, `tests/test_receipt.py`, `tests/test_calculator.py`, `tests/test_text.py`:
  pure `core/` logic.
- `tests/test_app.py`: headless UI tests with Streamlit's `AppTest` (including that user text is shown
  literally). PDF upload and `st.data_editor` interactions are not supported by `AppTest`; check those
  in a browser.
- `tests/test_streamlit_config.py`, `tests/test_requirements.py`, `tests/test_no_personal_data.py`:
  keep the security settings, version pins and the absence of personal data in place.
- Optional real-receipt test: set `ICA_SAMPLE_PDF` to a local receipt (and `ICA_SAMPLE_TOTAL` to its
  "Betalat" amount, e.g. `1122.17`) to run it; it is skipped otherwise.

Known limitations
- No authentication (see Project); the app is protected only by listening on localhost.
- `expenses.db` is not encrypted.
- `st.tabs` runs both tabs on every rerun, so the History query also runs while editing a receipt.
  Accepted for now.

Project structure
/
├── app.py
├── .streamlit/
│   └── config.toml     # Security settings (localhost only, upload size, error details)
├── integrations/
│   └── db.py
├── core/
│   ├── constants.py
│   ├── parser.py
│   ├── receipt.py
│   ├── calculator.py
│   └── text.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_calculator.py
│   ├── test_db.py
│   ├── test_no_personal_data.py
│   ├── test_parser.py
│   ├── test_receipt.py
│   ├── test_requirements.py
│   ├── test_streamlit_config.py
│   └── test_text.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── expenses.db         # Auto-generated on first run (not committed)

Setup
pip install -r requirements.txt

Run (from the repository root, so .streamlit/config.toml is used)
python -m streamlit run app.py
