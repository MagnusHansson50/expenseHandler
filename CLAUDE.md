Project
ExpenseHandler: a Streamlit web application for tracking personal spending.
Users upload grocery receipts (ICA PDFs, to begin with), add manual purchases,
categorize items, and save them to a history so they can follow up on their expenses.

The app supports MULTIPLE USERS, and each user's data (categories, item memory,
history) is COMPLETELY ISOLATED from every other user's.

Code location
All new code lives in this repository (`C:\Git\ExpenseHandler`).
`[removed]` is an older receipt-splitter prototype,
kept for reference only (e.g. its ICA parsing logic). Never write to it.

Tech stack
- Python 3.12+
- Streamlit (web UI and state management)
- Pandas (data manipulation and tables)
- PyPDF2 (PDF text extraction)
- SQLite3 (local persistent database)

Code conventions
- Language: UI text, variable names, comments and DataFrame columns in English.
- Naming: `snake_case` for functions and variables.
- Modularization: each database operation (init, create, load, save, delete) is its own function.
- `core/` modules are pure Python: no Streamlit imports, they take and return Pandas DataFrames.

Architecture
- `app.py`: UI only (sidebar user handling, tabs, forms, tables, charts).
- `integrations/db.py`: all SQLite access.
- `core/parser.py`: ICA PDF parsing.
- `core/calculator.py`: totals and per-category summaries.
- Connection handling: SQLite connections must use `check_same_thread=False`.
- State management: rely on `st.session_state` to prevent UI freezes and data loss on re-render.
  - `current_user`: id of the selected user. Nothing but the sidebar is shown until a user is selected.
  - `receipt_df`: the receipt currently being edited.
  - `table_version`: part of the `st.data_editor` key; bump it to force a rebuild of the table.

Database (`expenses.db`)
Every table except `users` MUST be tied to a `user_id`, and every query on those tables MUST filter on it.
1. `users` (id, name) - name is unique.
2. `categories` (name, user_id) - unique on (name, user_id).
3. `memory` (item, category, user_id) - unique on (item, user_id); remembers the last category chosen for an item.
4. `history` (id, date, item, price, category, user_id)
- Creating a user automatically seeds a default set of categories (Dairy, Pantry, Fruit, Vegetables, Other, ...).
- Always use `CREATE TABLE IF NOT EXISTS`. Keep the schema stable.
- The legacy `kvitto_minne.db` (tables `minne`, `kategorier`, `historik`) belongs to the old receipt-splitter version and is not used.

PDF parsing
- `parse_pdf(file_bytes)` reads the upload via `io.BytesIO` and PyPDF2.
- Designed specifically for the ICA receipt format: process line by line, pick up item lines ending in
  `st` or `kg`, parse the price, and capture discounts (negative amounts).
- Returns a DataFrame with the columns `Item` and `Price`.

UI
- Sidebar: dropdown to select an existing user, text field to create a new one.
- Tab "🛒 Current Receipt": add/remove categories, manual entry (item, price, category), PDF upload,
  `st.data_editor` for the current list, date picker + save button that writes to `history`
  and learns category choices into `memory`.
- Tab "📜 History": pick a start and end date, show total spent and an `st.bar_chart` per category.

Rules
- Do not break Streamlit's reactive loop. Use `st.form` for input and `st.session_state` for anything
  that triggers heavy updates.
- All file operations on uploaded PDFs must use `io.BytesIO`.
- Never read or write another user's rows: every function in `db.py` except the `users` functions takes `user_id`.

Build plan
The app is built in phases, one at a time, with approval before moving on:
1. Database layer (`integrations/db.py`)
2. PDF parser (`core/parser.py`)
3. Calculation logic (`core/calculator.py`)
4. UI shell and user handling (`app.py`)
5. UI: input tab
6. UI: history tab

Project structure
/
├── app.py
├── integrations/
│   └── db.py
├── core/
│   ├── parser.py
│   └── calculator.py
├── requirements.txt
└── expenses.db         # Auto-generated on first run

Setup
pip install -r requirements.txt
# Alternatively: pip install streamlit pandas PyPDF2

Run
python -m streamlit run app.py
