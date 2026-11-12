Project
ExpenseHandler: a Streamlit web application for tracking personal spending.
Users upload receipts (PDF receipt copies from Kivra or digital receipts from Willys), add manual purchases,
categorize items, and save them to a history so they can follow up on their expenses.

The app supports MULTIPLE USERS, and each user's data is COMPLETELY ISOLATED from every other user's.
"Isolated" means all data is user-specific: categories, which category an item belongs to (memory),
and history. No function may read or change another user's rows, and an action by one user
(e.g. deleting a category) never affects another user's data.
Every user logs in with a name and password (see Authentication), so nobody can open another
user's receipts from the app. The app still only listens on localhost (see Security).
It is distributed as a Windows desktop program (see Desktop program): everyone runs their own copy,
with their data on their own computer.

Code location
All code lives in this repository. The repository is public on GitHub (see Security).

Tech stack
- Python 3.12+
- Streamlit (web UI and state management)
- Pandas (data manipulation and tables)
- pypdf (PDF text extraction; replaces the unmaintained PyPDF2)
- SQLite3 (local persistent database)
- pytest (tests, dev only)
- Ruff (linter, dev only; settings in `pyproject.toml`)
- PyInstaller (builds the desktop program, build only: `requirements-build.txt`)
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
  `db.Login(user, password_hash, salt)`,
  `core.parser.ParsedReceipt(items, purchase_date, paid_total)`, `services.receipts.ImportResult(items,
  remembered, purchase_date, paid_total)`. Use the field names (`user.name`), never positions (`user[1]`).
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
- `services/auth.py`: `register`, `authenticate` (with the login throttle), `reset_password` and
  `delete_account`.
- `services/receipts.py`: flows that combine `core/` logic with the database, with no Streamlit:
  `import_receipt` (parse PDF, load memory, categorize -> `ImportResult`) and
  `save_receipt(user_id, purchase_date, draft, kept_in_fallback)` (validate ->
  `InvalidReceipt(problems)`, or save history and memory in one transaction; items that still need
  a category are not remembered, see Reviewing items without a category).
- `integrations/db.py`: all SQLite access, and the data rules that must always hold (see Database).
- `core/constants.py`: shared constants and input limits. Imports nothing, so every module may depend on it.
- `core/parser.py`: reads a receipt PDF, picks its layout (`FORMATS`) and reads the purchase date.
- `core/receipt_formats/`: one module per receipt layout (`kivra.py`, `willys.py`), each with `matches`,
  `parse_items` and `parse_paid_total`; `common.py` has what they share.
- `core/receipt.py`: logic for the receipt being edited (normalize, add rows, apply `st.data_editor`
  changes, categorize from memory, validate before saving, decide what to remember on save, find
  items that still need a category: `uncategorized_items`, `set_item_category`, `item_total`,
  `item_rows`, and `remove_row` / `remove_item` for removing items).
- `core/backup.py`: the backup file (write, read and check), the CSV export and the import merge
  rules (see Backup and CSV export).
- `services/backup.py`: `export_backup`, `export_history_csv`, `import_backup`.
- `core/history.py`: `category_changes` - which saved purchases got another category in the
  history list (editor rows -> history ids, labels -> stored names, unchanged left out);
  `filter_categories` / `filter_by_categories` for the History tab's category filter.
- `services/history.py`: `change_categories(user_id, history, editor_changes, lang)` - saves them
  with `db.update_history_categories` (nothing is written if nothing changed).
- `core/calculator.py`: totals, per-category summaries and `paid_difference` (items vs. the paid total).
- `core/text.py`: `escape_markdown` for showing user-provided text safely.
- `core/categories.py`: `category_clash(name, categories)` -> `CategoryClash(existing, exact)` or
  `None`, `comparable` (letter case and extra spaces ignored) and `is_reserved` (the fallback
  labels), for asking before adding a category that looks like an existing one.
- `core/auth.py`: password hashing and checking (`hash_password`, `verify_password`) and password
  rules (`password_problem`).
- `scripts/reset_password.py`: command-line tool for whoever runs the app to set a new password
  (see Authentication). Not imported by the app.
- `desktop/launcher.py`: entry point of the desktop program (see Desktop program). Imports
  `core.i18n`, `scripts` and Streamlit; nothing in the app imports `desktop/`.
- `desktop/ExpenseHandler.spec`, `desktop/smoke_test.py`: the PyInstaller build and the check that a
  built program starts and answers.
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
  - `current_user`: id of the logged-in user, or `None`. Set ONLY by `log_in` (via `switch_user`)
    after `authenticate` or `register` succeeded, and cleared by `log_out`;
    `tests/test_auth_guards.py` checks this. Nothing but the language selector and the login page
    is shown while it is `None`. Logging in or out clears the unsaved receipt.
  - `auth_message`: (form, translation key, params) for the login, register or delete-account form
    (`"login"`, `"register"`, `"delete"`), shown once.
  - `login_name`, `login_password`, `register_name`, `register_password`, `register_password_repeat`,
    `delete_password`, `delete_confirm`: the login and account form fields. The password fields are emptied in the submit callback (`take_password`),
    so a password never stays in session state.
  - `receipt_df`: the receipt currently being edited (single source of truth for the table).
  - `table_version`: part of the `st.data_editor` key (together with the language). Edits are folded
    into `receipt_df` in the editor's `on_change`, then the version is bumped so the table is rebuilt
    and no edit is applied twice.
  - `upload_version`: part of the `st.file_uploader` key; bumped after a PDF is parsed so the same file
    is not parsed again on the next rerun.
  - `backup_upload_version`: the same for the backup uploader.
  - `history_version`: part of the history list's `st.data_editor` key (with the language and the
    period); bumped after saving changed categories, so the list is rebuilt from the database.
  - `paid_total`: the amount paid on the uploaded receipt(s) in the draft, to compare the list with
    while editing (`render_paid_comparison`); a second upload into the same list adds its amount,
    and it is `None` when there is nothing to compare with (no upload, a receipt without a paid
    amount, or items added before the upload). Reset when the draft becomes empty.
  - `imported_rows`, `removed_total`: the rows ([item, price]) that came from the uploaded
    receipt(s), and the amount of those removed since ("Remove an item", the popup's remove button
    or deleting rows in the table, all through `note_removed`). Removed on purpose means not
    missing, so the comparison uses the paid amount minus `removed_total` and says so; a row added
    by hand and removed again never counts. Reset with `paid_total`.
  - `purchase_date`: the date that will be saved with the receipt (from the receipt, or picked by the user).
  - `date_version`: part of the date picker key; bumped when `purchase_date` is set from code
    (upload, save, clear, switch user) so the picker shows the new value.
  - `flash`: (kind, message) shown once after the next `st.rerun()`. It is rendered in a container that
    exists on every run, so the tabs below never move (moving them resets the selected tab).
    It is also shown on the login page (e.g. after deleting an account).
  - `review_active`, `review_dismissed`, `review_handled`, `review_skipped`, `review_kept_fallback`,
    `review_names`, `review_notice`, `review_category_message`, `review_pending_category`: the review
    popup for items without a category (see below).
    They are reset when the draft becomes empty (cleared, saved, logging in or out).
  - `pending_category`: (new name, existing category) while "Manage categories" asks whether to add
    a name that looks like an existing category (see Look-alike categories). Cleared by the answer,
    a new name, logging in or out. `review_pending_category` is the same inside the review popup,
    also cleared when the review stops or starts.
  - `history_categories`: the categories (stored names) the History tab is filtered on; empty
    means all. Kept when the period or language changes, cleared on logging in or out. The
    multiselect (`history_filter`) is set from it on every run, leaving out what it does not
    offer for this period, and its `on_change` copies the choice back and bumps `history_version`.

Database (`expenses.db`)
Every table except `users` MUST be tied to a `user_id`, and every query on those tables MUST filter on it.
1. `users` (id, name) - name is unique, regardless of letter case ("Anna" / "anna", "Åsa" / "åsa";
   checked in Python with `casefold()` because SQLite's `NOCASE` only folds A-Z).
2. `categories` (name, user_id) - unique on (name, user_id).
3. `memory` (item, category, user_id) - unique on (item, user_id); remembers the last category chosen for an item.
4. `history` (id, date, item, price, category, user_id) - date stored as `YYYY-MM-DD` text.
5. `credentials` (user_id, password_hash, salt) - one row per user, removed with the user.
   Only the scrypt hash and salt are stored, never the password.
- `create_user(name, default_categories)` seeds the user's starting categories (the app passes
  `core.i18n.DEFAULT_CATEGORIES[language]`) and always adds `FALLBACK_CATEGORY`. Name errors are
  `UserNameEmpty`, `UserNameTooLong`, `UserNameTaken` (all `UserNameError`, a `ValueError`).
  `create_user_with_password` does the same and stores the credentials in the same transaction;
  the app only uses this one (through `services.auth.register`).
- `get_login(name)` returns `Login(user, password_hash, salt)`, or `None` for an unknown name or a
  user without a password. The name must match exactly (surrounding spaces ignored, case not).
  `set_password(user_id, ...)` adds or replaces a password and returns `False` for an unknown user.
- `get_all_history(user_id)` returns all of a user's purchases, oldest first (for backups).
  `import_user_data(user_id, categories, memory, history_df)` adds them in one transaction (see
  Backup and CSV export).
- `update_history_categories(user_id, categories_by_id)` gives saved purchases (history ids) a
  new category and remembers it for their items, in one transaction. Only the user's own rows
  (`WHERE id = ? AND user_id = ?`); other ids are skipped. A category the user does not have becomes
  `FALLBACK_CATEGORY`, which is remembered too (it was chosen). Returns how many purchases changed.
  Only the category of a saved purchase can be changed, never its date, item or price.
- `delete_user(user_id)` deletes the user; their categories, memory, history and credentials go with
  them through `ON DELETE CASCADE` (foreign keys are on for every connection), in one transaction.
  It turns on `PRAGMA secure_delete` so the freed pages are overwritten and the data cannot be read
  back from the file. Returns `False` for an unknown user. The name can be registered again.
- `FALLBACK_CATEGORY` is stored as "Other" in every language and can never be deleted;
  `delete_category` refuses it. Its labels in every language ("Övrigt", "Other") are reserved:
  `add_category` rejects them in any letter case.
- Deleting a category also deletes that user's `memory` rows pointing at it, in the same transaction.
  Deleting a category never rewrites `history`: saved purchases keep the category they were saved
  with (the user can change it in the history list, see `update_history_categories`). In the UI,
  rows of the unsaved receipt in that category move to `FALLBACK_CATEGORY` (`core.receipt.clear_category`,
  in `remove_category`), so the table never shows a category the user no longer has. Removing a
  category needs a ticked confirmation box, in "Manage categories" and in the review popup alike.
- Look-alike categories: `categories` is unique on the exact name, so "mjölk" next to "Mjölk" is
  allowed in the database. The UI asks first (`app.add_category` returns kind `"similar"`):
  "You already have the category 'Mjölk'. Add 'mjölk' anyway?" with "Add anyway" / "Cancel", in
  "Manage categories" and in the review popup alike; nothing is added until "Add anyway". Names are
  compared with `core.categories.comparable` (casefold, extra whitespace ignored). An exact
  duplicate gets its own message (`category_exists`); the reserved fallback labels skip the
  question and get the usual refusal. Backup import adds only missing exact names and asks nothing.
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
- Schema version: the file carries `PRAGMA user_version` (`db.SCHEMA_VERSION`, now 1), because desktop
  users keep their `expenses.db` across program versions. `init_db` stamps new files and files from
  before versioning (0). To change the schema, leave the `CREATE TABLE` script as version 1, add the
  change as `db._MIGRATIONS[n]` (a function taking the open connection) and set `SCHEMA_VERSION = n`;
  `init_db` runs the missing migrations in order in one transaction with the new version. A file
  with a higher version raises `db.DatabaseTooNew` (key `database_too_new`) before anything is
  changed; the app shows that message instead of the login page and the reset script exits with 3.
  The version is written with an f-string only because PRAGMA takes no `?` parameters; it is an int
  constant.
- The `EXPENSES_DB_PATH` environment variable points the app at another database file
  (used for manual testing; the test suite patches `db.DB_PATH` instead). `db.database_path(env)`
  reads it: surrounding spaces are removed, and an empty or blank value counts as not set
  (`DEFAULT_DB_PATH`, `expenses.db` next to the code); the launcher's `use_data_dir` does the same.
- The legacy `kvitto_minne.db` (tables `minne`, `kategorier`, `historik`) belongs to the old receipt-splitter version and is not used.

PDF parsing
- `read_receipt(file_bytes)` reads the upload via `io.BytesIO` and pypdf and returns
  `ParsedReceipt(items, purchase_date, paid_total)` - a DataFrame with `Item` and `Price`, the date
  printed on the receipt and the amount paid (each `None` if not found). The app calls it through `services.receipts.import_receipt`.
- Bytes that do not start with `%PDF-` raise `NotAPdfError` before pypdf sees them. Any error raised by
  pypdf itself becomes `ReceiptReadError` (the pypdf exception is kept as `__cause__`).
- Layouts: one module per receipt layout in `core/receipt_formats/`, each with `matches(text)`,
  `parse_items(text)` and `parse_paid_total(text)`. `core.parser.FORMATS` lists them in the order
  they are tried (`kivra`, `willys`); the first whose `matches` is true parses the text. Text in no
  layout raises `UnknownReceiptFormat` (key `unknown_receipt_format`, not logged). To add a layout:
  a new module with those three functions, an entry in `FORMATS`, a `tests/test_<name>_format.py`
  with made-up text in the layout, the texts that name the supported receipts (`upload_label`,
  `not_a_pdf`, `pdf_unreadable`, `unknown_receipt_format`) and README. Make `matches` specific:
  it must not accept another layout's text.
- Kivra (`kivra.py`, recognized by the column header `Beskrivning Artikelnummer ...`): Kivra's
  receipt copies print every store's receipt (ICA, Jula, Kjell & Co, Rusta,
  Stadium, ...) with the same columns: name, article number, unit price, quantity, `st`/`kg`, total.
  Process line by line, pick up item lines ending in those columns, parse the total, and capture
  discounts (negative amounts), which are merged into the item above. So is a deposit line without
  article number or unit (`*Pant  40,00 1 40,00`, `Pant  2,00 2 4,00`) below a drink. Back-to-back lines with the
  same article number are combined into one row.
  A name too long for one line is printed on the line(s) above, with the columns alone on the last
  line; those name lines are joined. The column header and
  discounts clear the collected lines, so store and address lines never become a name.
  Parsing stops at the payment section (`Delavstämning`, `Betalat`, `Betalningsinformation`).
  The amount paid is the `Betalat` line.
- Willys (`willys.py`, recognized by `Totalt N varor` together with `Totalt 206,60 SEK`): a copy of
  the till receipt in fixed-width text. An item line ends in its amount, with an optional
  `4st*23,90` before it (not part of the name). Indented lines below an item (and, should
  extraction drop the spaces, lines starting with `+` or ending in a negative amount) belong to
  it: discounts (`Rabatt:DRYCK -4,18`) and deposits (`+PANT ... 6,00`) are merged into it. A
  discount larger than the item above (a multi-buy covering several items, `Willys Plus:CHOKLAD
  -34,50`) becomes its own row, so no item gets a negative price. A line without an amount followed
  by an indented amount is read as a weighed item (not yet seen on a real receipt). Items end at
  `Totalt N varor`; `Totalt ... SEK` is the amount paid. Only self-checkout receipts have been seen.
- The purchase date is the first valid `YYYY-MM-DD` in the text; text extraction may glue it to a label
  (e.g. `Kassör2026-09-26`).
- After an upload the app compares the items with the amount paid (`paid_difference`); if they
  differ, the import message is a warning saying how much less or more the list is
  (`paid_items_missing` / `paid_items_too_much`) and where to add or remove an item. Below the
  total the same comparison stays while editing (`paid_total`), so adding the missing item or
  removing an extra one turns it into "✔️ The list matches ..." (`paid_matches`). Items removed
  from the receipt on purpose are taken off the paid amount ("... minus what you removed (25,00 kr)").

Backup and CSV export
- Only the logged-in user's own data. `services/backup.py`: `export_backup(user_id)` (JSON bytes),
  `export_history_csv(user_id, lang)` and `import_backup(user_id, data)` -> `db.ImportCounts(categories,
  memory, purchases)`, raising `core.backup.InvalidBackup(problems)` (nothing added) for a bad file.
- File format (`core/backup.py`): JSON with `format` ("expensehandler-backup"), `version`
  (`BACKUP_VERSION`, now 1), `exported`, `categories` (stored names), `memory` (item -> category) and
  `history` (date, item, price, category). Never passwords. A newer version is refused
  (`backup_too_new`); when the format changes, bump `BACKUP_VERSION` and keep reading older versions.
- `read_backup` checks everything before anything is written and reports every problem at once as
  `Problem` keys (`backup_*`, and the receipt's item/price problems with the entry's row number):
  at most `MAX_BACKUP_BYTES` (5 MB), JSON that is not nested too deep, the format and version,
  category names (length, reserved labels), memory, and each purchase's fields, types,
  `YYYY-MM-DD` date and limits. Names in the problems come from the file: the UI escapes them.
- Import merges (`new_categories`, `new_memory`, `new_history_rows`): missing categories are added,
  the user's own remembered choices win, and purchases are compared on (date, item, price,
  category) and counted, so identical purchases stay separate and importing the same file twice adds
  nothing. `db.import_user_data` writes it all in one transaction with the usual rules (a category the
  user does not have becomes `FALLBACK_CATEGORY`).
- CSV: Swedish uses `;` and decimal commas, English `,` and points; UTF-8 with BOM; categories as
  labels. Text cells starting with `=`, `+`, `-`, `@`, tab or CR get a leading `'` (CSV injection);
  prices are written as numbers. It is for reading only; there is no CSV import.
- UI: History tab, collapsed "💾 Backup" ("💾 Säkerhetskopia"), shown also without history: download
  buttons (file names from `download_name`, e.g. `ExpenseHandler-Anna-2026-11-05.json`) and an
  uploader keyed with `backup_upload_version` so a file is imported once. Success is a flash with the
  counts; problems are listed (at most 20) next to the uploader.

Desktop program
- `desktop/launcher.py` starts the app: it sets `EXPENSES_DB_PATH` to the user's data folder
  (`%APPDATA%\ExpenseHandler\expenses.db`; `~/Library/Application Support/...` on macOS,
  `$XDG_DATA_HOME` or `~/.local/share/...` on Linux) unless it is already set, picks a free port
  (or `--port N`), prints where it runs (sv and en, `desktop_running`), opens the browser once
  `/_stcore/health` answers (not with `--no-browser`), and runs Streamlit. `--reset-password "Name"`
  runs `scripts/reset_password.py` on the same database.
- `.streamlit/config.toml` is not read inside a packaged program, so `streamlit_flags()` passes the
  security settings as flags (localhost, 5 MB uploads, no error details) plus no usage statistics,
  no file watching and `global.developmentMode` off (Streamlit guesses dev mode when it is not in
  `site-packages`, as in a bundle, and would load its UI from a dev server). Keep them in sync with
  `config.toml`; `tests/test_launcher.py` compares them. `start_streamlit` loads the flags with
  `bootstrap.load_config_options` before `bootstrap.run`, as `streamlit run` does; `bootstrap.run`
  alone ignores them.
- Build: `python -m pip install -r requirements-build.txt`, then
  `python -m PyInstaller desktop/ExpenseHandler.spec --noconfirm` -> `dist/ExpenseHandler/`
  (`ExpenseHandler.exe` and `_internal/`, about 200 MB; one folder, not one file, for start-up time
  and fewer antivirus alarms). Streamlit has no PyInstaller hook: the spec collects its data files,
  metadata and submodules, copies `app.py` as a file and lists our packages as hidden imports
  (Streamlit runs `app.py` as a script, so PyInstaller cannot see its imports). A new top-level
  package must be added to the spec. `streamlit/.agents` (templates for AI assistants, unused) is
  left out: its 138-character paths made unzipping fail under Windows' 260-character limit in a
  deep folder; keep the longest path in the bundle near 100 characters. `build/` and `dist/` are
  ignored by git.
- Check a build: `python desktop/smoke_test.py dist/ExpenseHandler/ExpenseHandler.exe` (starts it with
  a throwaway database and waits for the health endpoint and the page). PDF upload and the data
  editor still need a manual check in the built program.
- GitHub Actions: `.github/workflows/tests.yml` runs for pushes to master and pull requests, as
  three jobs that each wait for the one before: `lint` (Ruff, Ubuntu), `test` (pytest on Windows and
  Ubuntu, Python 3.12) and `build` (Windows: PyInstaller, smoke test, and the program uploaded as
  the artifact `ExpenseHandler-windows`, kept 7 days; nothing is published).
  `.github/workflows/release.yml` runs on a pushed tag `v*`: Ruff, tests, build, smoke test, then
  `ExpenseHandler-<tag>-windows.zip` on a new GitHub release. Actions are pinned to commit SHAs (tag
  in a comment); the tag name reaches scripts only through `$env:TAG`. No secrets are needed (only
  the automatic `GITHUB_TOKEN`). Pushing a tag publishes a release, so only do it when the user asks.
- There is no cloud deployment, on purpose: the app must only listen on localhost (see Security),
  and hosting it would need HTTPS, closed registration, a shared throttle and server-side storage
  of everyone's receipts first. The "deployment" is the GitHub release of the desktop program.

Authentication
- Login is by user name and password; there is open registration (anyone who can open the app can
  create an account). Passwords are 8-128 characters (`MIN_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH`).
- Hashing (`core/auth.py`): scrypt (n=2**14, r=8, p=1, 64-byte hash, random 16-byte salt per
  password), NFKC-normalized before hashing, compared with `hmac.compare_digest`. Passwords longer
  than the maximum are rejected without hashing.
- `services.auth.authenticate(name, password)` returns the `User` or `None`. A wrong password and an
  unknown name give the same result and message ("Wrong user name or password.") and take about
  the same time (an unknown name is checked against a dummy hash).
- Throttle: after `MAX_FAILED_LOGINS` (5) failures in a row a name is locked for `LOCK_SECONDS` (30),
  even for the right password (`LoginLocked(seconds_left)`). Kept per name (case-insensitive) in
  `services.auth.login_throttle`, in server memory; a success resets it. Tests get a fresh throttle
  from an autouse fixture in `tests/conftest.py`.
- Passwords are never logged, printed, put in the URL or kept in session state; only the hash and
  salt are stored. `tests/test_auth_guards.py` checks that no log or print call in the login code
  mentions a password or salt.
- Forgotten password: the app cannot send e-mail, so whoever runs it sets a new one on the same
  computer: `python scripts/reset_password.py "<user name>"` (asks twice with `getpass`; uses
  `EXPENSES_DB_PATH` if set). Its messages are in English (admin tool). A file SQLite cannot open
  or write (a missing folder, a locked or damaged file) gives a short message and exit code 4
  (`EXIT_DATABASE_ERROR`) instead of a traceback, before any password is asked for.
- The session lasts while the browser tab is open; a reload or a new tab starts logged out.
- Deleting an account: `services.auth.delete_account(user_id, password)` checks the password again
  through `authenticate`, so wrong passwords count towards the same lock as logins, and only then
  calls `db.delete_user`. The UI also requires a ticked confirmation box. Afterwards the user is
  logged out; other tabs of the same user are logged out on their next rerun (the user no longer
  exists). There is no undo and no export first.

UI
- Not logged in: the language selector in the sidebar and a login page with the tabs "Log in" and
  "Create account". Nothing about other users (not even their names) is shown. The login page is
  one `st.container()` in the place where the app's tabs come after logging in, so the next run
  replaces it at once; as separate elements, the old login box was pushed down below the new tabs
  until the run ended (`tests/test_app_login.py` checks the position).
- Logged in: the sidebar shows the language selector, "Logged in as <name>", a "Log out" button and
  a collapsed "🗑️ Delete my account" ("🗑️ Ta bort mitt konto") section: a warning, the password, a
  confirmation box and a delete button. The login page then shows "Your account and all your
  receipts have been deleted."
- Tab "🛒 Current Receipt" ("🛒 Aktuellt kvitto"): add/remove categories, manual entry (item, price,
  category; "✍️ Add a purchase manually" above the upload while the list is empty, then "➕ Add a
  missing item" below the table, the same form), PDF upload
  (categories pre-filled from the user's memory, purchase date from the receipt), `st.data_editor`
  for the current list (a caption above it says items, prices and categories can be changed there
  and where to add a missing item; rows can also be added and deleted in the table itself),
  a collapsed "🗑️ Remove an item" ("🗑️ Ta bort en vara") section below it (a list of the rows as
  "Row 3: Milk – 15,90 kr", so rows with the same name can be told apart, and a remove button;
  the widget key holds `table_version`; the labels are worked out before the selectbox, since
  `AppTest` calls its `format_func` outside a run), date picker + save button that writes to
  `history` and learns category choices into `memory`. A removed row is never saved or remembered.
  Save is blocked with the per-row list of problems from `InvalidReceipt`.
  Above the table: the button that opens the review popup for items without a category.

Reviewing items without a category
- An item needs a category (`core.receipt.uncategorized_items`) when its category is missing or no
  longer one of the user's, or when it is `FALLBACK_CATEGORY` although memory does not say the user
  chose that for it. Items filed under "Other" on purpose are not asked about again.
- The review is a popup (`st.dialog`, "🏷️ Items without a category"): a progress bar ("Item 2 of
  5"), the item and its amount, the user's categories as clickable tags (`st.pills`, a new key per
  item so no choice carries over) and "Skip" / "🗑️ Remove from receipt" / "Stop". Remove
  (`review_remove`, a callback like the choices) takes every row with that name off the receipt
  (`core.receipt.remove_item`); it is never saved or remembered, and the popup moves on (or closes
  if the receipt is now empty). One click on a tag gives every row with
  that name the category and moves on. "Stop" and the window's X (`on_dismiss=close_review`) keep
  what was chosen and put the items left in `review_dismissed`. When every item is handled the popup
  closes and a flash says so, or how many were skipped. It never blocks saving.
- Categories in the popup: a "New category" field adds one (it becomes a tag; it is not chosen for
  the item shown), and a collapsed "🗑️ Remove a category" section removes one (a list without the
  fallback category, a confirmation box). Both use `add_category` / `remove_category` in `app.py`,
  shared with "Manage categories", are handled at the top of the popup's next run
  (`handle_review_category_forms`) so the tags are reloaded there, keep the popup on the
  same item, and show their result once inside the popup (`review_category_message`), since a flash
  would be hidden behind it. Items already given a removed category in this review move to the
  fallback category and are taken out of `review_handled`, so they are asked about again.
  A look-alike name asks "Add anyway?" inside the popup (`review_pending_category`); its two
  buttons are read in `handle_review_category_forms` too, so the popup stays on the same item.
- It opens by itself after a PDF upload in which some items got no category from memory, and then
  shows the import message at its top (`review_notice`), because it covers the flash. It does not
  open by itself for items added by hand (the form defaults to the fallback category). Above the
  table, "🏷️ Go through items without a category (N)" opens it at any time; N leaves out items
  put in "Other" on purpose in the popup.
- How the popup works: it stays open across reruns because `render_review` calls it while
  `review_active` is true. A click inside a dialog reruns only the dialog function, so the dialog
  works out everything itself from session state and the database (categories, the items left,
  forms sent on the previous click), and choices and skips are made in callbacks (`on_change` /
  `on_click`). Do NOT call `st.rerun()` for a choice: that closes and reopens the popup, which
  flickers. Only closing it (Stop, the last item) reruns the whole app, which also updates the table
  behind it. `st.rerun(scope="fragment")` is not an option: it raises in `AppTest`, which reruns
  the whole script. `AppTest` renders the popup and its tags; the X and the absence of flicker are
  checked in a browser.
- Memory: items that still need a category when the receipt is saved are saved to history but not
  remembered, so they are asked about next time. Choosing "Other" in the review is a choice
  (`review_kept_fallback`) and is remembered. "Other" picked in the table or left as the manual
  form's default is not (it cannot be told apart from the default). Changing a saved purchase's
  category in the History list is a choice too and is remembered (also "Other").
- Tab "📜 History" ("📜 Historik"): pick a start and end date and optionally some categories
  ("Categories", empty = "All categories"; the user's categories plus removed ones still used in
  the period, as labels; `history_categories`), show total spent, an `st.bar_chart` per category,
  the list of purchases (an `st.data_editor` in a form where only the category can be changed, a
  selectbox of the user's categories as labels; "💾 Save changes" saves them through
  `services.history.change_categories` and remembers them, see `db.update_history_categories`), delete all purchases saved on a date (with confirmation), and the backup
  section (see Backup and CSV export). The category filter applies to the total, the count
  (with "Showing 2 of 9 categories."), the chart and the list, which is numbered from 0 again
  because `category_changes` maps editor rows by position. Deleting a date ignores it (and says
  so), and so do backups and the CSV export.

Languages
- Supported: Swedish (`sv`, the default) and English (`en`), listed in `core.i18n.LANGUAGES`.
- Where the language is kept: `st.session_state.language` and the URL (`?lang=sv`). On the first run
  in a browser tab it is read from `?lang=` (unknown values fall back to Swedish); after that the
  selector writes it back to the URL, so a reload or bookmark keeps it. It is NOT stored per user:
  a new tab without `?lang=` starts in Swedish, and switching user keeps the tab's language.
- Adding or changing a text: add the same key to every language in `core.i18n.TRANSLATIONS`, with the
  same `{placeholders}`, and use it with `t("key", lang())`. `tests/test_i18n.py` fails if a key is
  missing in a language, has different placeholders, or is defined but never used (it scans `app.py`,
  `desktop/launcher.py` and the keys produced in `core/` (receipt, auth, backup) and `db.py`).
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
  problems from `InvalidReceipt`, `NotAPdfError`, `UnknownReceiptFormat`, duplicate user name, `DatabaseTooNew`).

Security
- Network: `.streamlit/config.toml` sets `server.address = "localhost"`. The login is not hardened
  for a network (no HTTPS, open registration, see Known limitations), so the app must never listen
  on other interfaces. Do not remove this or start the app with `--server.address`.
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
- Never read or write another user's rows: every function in `db.py` except the `users` functions
  (create, look up by id or name, `get_login`) takes `user_id`.
- Never put a password in a log, the URL, session state or the database; only `core/auth.py` hashes
  and checks passwords, and only `log_in` / `log_out` change `current_user`.
- New logic goes in `core/` with tests; flows that also need the database go in `services/`;
  `app.py` only wires them to the UI.
- Follow the Security section for anything that renders user text, accepts input or adds a dependency,
  and the Error handling section for anything that calls the database or an external library.

Testing
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Run: `python -m pytest`
- Lint: `python -m ruff check .` (`--fix` sorts imports). Rules in `pyproject.toml`: pycodestyle,
  pyflakes, import order and bugbear, 120-character lines (`core/i18n.py` excepted, its texts are
  whole sentences). `zip()` of columns gets `strict=True`. The CI stops before the tests on a lint
  error.
- `tests/test_db.py`: data layer, including user isolation, input limits, transactions and atomic
  `save_receipt`. Each test uses its own temporary database.
- `tests/test_db_update_categories.py`: changing the category of saved purchases (only the user's
  own, fallback for other categories, memory, all or nothing).
- `tests/test_parser.py`, `tests/test_kivra_format.py`, `tests/test_willys_format.py`,
  `tests/test_receipt.py`, `tests/test_calculator.py`, `tests/test_text.py`:
  pure `core/` logic.
- `tests/test_services.py`: `services/receipts.py` flows against a temporary database.
- `tests/test_history.py`, `tests/test_services_history.py`, `tests/test_app_history_edit.py`: which
  categories were changed in the history list, saving them, and the list in the UI (only the
  category editable, the save button, database errors). Picking a category in the table is
  checked in a browser (`AppTest` cannot edit `st.data_editor`).
- `tests/test_auth.py`, `tests/test_db_credentials.py`, `tests/test_services_auth.py`: password
  hashing, credential storage, registration, login and the throttle (with a fake clock).
- `tests/test_app_remove_item.py`: the "Remove an item" section (rows listed with their number, only
  that row removed, one of two rows with the same name, never saved or remembered). Deleting rows
  in the table itself is checked in a browser.
- `tests/test_app_missing_item.py`: where the manual form is, and the comparison with the amount
  paid while editing (missing, too much, matching, none without an upload, reset on clear).
- `tests/test_app_review.py`: the review popup for items without a category (the button and its
  count, one item at a time with tags, skip, stop, reopening, escaping, what is remembered on save,
  adding and removing categories in the popup, removing an item from the receipt).
  Opening by itself after a PDF upload is checked in a browser (`AppTest` cannot upload).
- `tests/test_app_history_filter.py`: the History tab's category filter (total, count, chart and
  list follow it, kept across period and language, removed categories, logout, other users).
- `tests/test_categories.py`, `tests/test_app_similar_category.py`: look-alike category names
  (which names clash, the question in "Manage categories" and in the popup, add anyway, cancel,
  only the user's own categories, escaping, Swedish texts).
- `tests/test_app_login.py`: the login page (same message for wrong password and unknown name,
  lockout, registration rules, logout, isolation between users, no password left in session state).
- `tests/test_reset_password_script.py`: the reset script with scripted password answers.
- `tests/test_db_delete_user.py`, `tests/test_app_delete_account.py`: deleting an account in the data
  layer (nothing left in any table or in the file, other users untouched) and in the UI
  (confirmation, wrong password, lock, logout, the name can be reused).
- `tests/test_auth_guards.py`: no password in logs; `current_user` only set by `switch_user`/`log_out`.
- `tests/test_backup.py`, `tests/test_services_backup.py`, `tests/test_app_backup.py`: the backup
  format and its checks, the CSV export (also CSV injection), the merge rules, export and import
  against a temporary database (one user's data only, twice adds nothing, all or nothing), and the
  UI section. Uploading a backup is not supported by `AppTest`; check it in a browser.
- `tests/test_db_schema.py`: schema version, migrations (once, in order, all or nothing) and refusing
  a database from a newer version.
- `tests/test_launcher.py`: the desktop launcher (data folders, port, flags matching `config.toml` and
  in effect when the server starts, `--reset-password`, `--port`, `--no-browser`).
- Tests use only made-up test passwords (`TEST_PASSWORD` in `tests/test_app.py`); UI tests register
  and log in through the forms with the helpers in `tests/test_app.py`.
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
- Optional real-receipt test: set `SAMPLE_RECEIPT_PDF` to one or more local receipt PDFs (Kivra or Willys)
  (separated by `;` on Windows, `:` elsewhere) to check that their items add up to `Betalat`;
  it is skipped otherwise. Never commit those files.

Known limitations
- Login protects users from each other inside the app; anyone on the computer can still read
  `expenses.db` directly. The app also only listens on localhost.
- Registration reveals whether a user name is taken.
- Anyone can lock a name for 30 seconds by entering a wrong password five times. There is no limit
  across different names, and the throttle starts over when the app restarts.
- No idle timeout: a session lasts as long as the browser tab stays open.
- Login names are case-sensitive ("anna" does not log in "Anna"), although registration treats
  them as the same name. Unicode look-alike names (e.g. Latin "a" vs Cyrillic "а") count as different.
- `expenses.db` is not encrypted.
- Passwords can only be changed with `scripts/reset_password.py`; there is no "change password" in
  the app. To delete an account whose password is forgotten, reset it first.
- The comparison with the paid amount while editing knows a removed row came from the receipt by
  its item name and price: a row whose name or price was changed before it was removed counts as
  missing. Uploading a receipt into a list that already has items added by hand shows no comparison.
- Only the category of a saved purchase can be changed; a wrong date, item or price means deleting
  that date's purchases and entering them again. A purchase saved with a category that was later
  removed shows the old name until it is changed (the list only offers current categories).
- Deleting an account cannot be undone; download a backup first to keep the history. Backups and
  copies of `expenses.db` made earlier still contain the deleted data.
- Backups are not encrypted and cannot be protected with a password, and they are not made
  automatically. There is no CSV import (only CSV export).
- If `expenses.db` is lost or damaged, whatever is not in a downloaded backup is gone. Copying the
  file while the app is stopped backs up all users at once.
- Only receipt copies from Kivra and digital receipts from Willys (PDF) can be imported; other
  receipts must be entered manually. Willys receipts have only been seen from the self-checkout.
  A layout that changes or a line the parser does not recognize shows up as a warning that the
  items do not add up to `Betalat`.
- PDF upload and `st.data_editor` edits are not covered by the automated tests (`AppTest` does not
  support them); check them in a browser after changing that code.
- The desktop program exists only for Windows, is not code-signed (Windows shows "Windows protected
  your PC" on first start), does not update itself, is about 200 MB, and runs in a console window
  that must stay open. Mac and Linux users run it from the code (`python desktop/launcher.py`).
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
├── README.md           # For users, in Swedish: run, log in, reset password, limitations
├── .streamlit/
│   └── config.toml     # Security settings (localhost only, upload size, error details)
├── requirements-build.txt  # PyInstaller pin for the desktop build
├── pyproject.toml      # Ruff settings (the app is not a package)
├── .github/
│   └── workflows/
│       ├── tests.yml   # Ruff, pytest on Windows and Ubuntu, build and smoke test
│       └── release.yml # build, smoke test and release on a v* tag
├── desktop/
│   ├── __init__.py
│   ├── launcher.py     # Entry point of the desktop program
│   ├── ExpenseHandler.spec  # PyInstaller build
│   └── smoke_test.py   # Check that a built program starts
├── services/
│   ├── auth.py         # Register, log in (with throttle), reset password, delete account
│   ├── backup.py       # Export and import of a user's own data
│   ├── history.py      # Change the category of saved purchases
│   └── receipts.py     # Import and save flows (core + database, no Streamlit)
├── scripts/
│   ├── __init__.py
│   └── reset_password.py  # Set a new password from the command line
├── integrations/
│   └── db.py
├── core/
│   ├── auth.py         # Password hashing and rules
│   ├── categories.py   # Look-alike category names
│   ├── backup.py       # Backup file format, CSV export, import merge rules
│   ├── history.py      # Category changes and the category filter in the history
│   ├── constants.py
│   ├── parser.py       # Reads the PDF, picks the layout
│   ├── receipt_formats/  # One module per receipt layout (kivra.py, willys.py)
│   ├── receipt.py
│   ├── calculator.py
│   ├── i18n.py         # Translations, number formatting, categories per language
│   └── text.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_app_backup.py
│   ├── test_app_db_errors.py
│   ├── test_app_delete_account.py
│   ├── test_app_history_edit.py
│   ├── test_app_history_filter.py
│   ├── test_app_language.py
│   ├── test_app_login.py
│   ├── test_app_missing_item.py
│   ├── test_app_remove_item.py
│   ├── test_app_review.py
│   ├── test_app_similar_category.py
│   ├── test_architecture.py
│   ├── test_auth.py
│   ├── test_auth_guards.py
│   ├── test_backup.py
│   ├── test_calculator.py
│   ├── test_categories.py
│   ├── test_db.py
│   ├── test_db_credentials.py
│   ├── test_db_delete_user.py
│   ├── test_db_schema.py
│   ├── test_db_update_categories.py
│   ├── test_history.py
│   ├── test_i18n.py
│   ├── test_launcher.py
│   ├── test_no_personal_data.py
│   ├── test_kivra_format.py
│   ├── test_willys_format.py
│   ├── test_parser.py
│   ├── test_receipt.py
│   ├── test_requirements.py
│   ├── test_reset_password_script.py
│   ├── test_services.py
│   ├── test_services_auth.py
│   ├── test_services_backup.py
│   ├── test_services_history.py
│   ├── test_streamlit_config.py
│   └── test_text.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── expenses.db         # Auto-generated on first run (not committed)

Commits
- Commit messages are in English: a short summary line, a blank line, then what changed and why.
- Work done as a numbered plan uses a prefix with the plan's name and step number, e.g.
  `Code Quality Step 3: handle database errors in the UI with retry`, `Security step 2: ...`,
  `Language Step 5: ...`, `Login Step 4: ...`, `Desktop Step 2: ...`, `Backup Step 3: ...` or
  `Popup Step 1: ...`, `Popup Categories Step 2: ...`, `Receipt Format Step 2: ...` or
  `Edit Category Step 1: ...` or `Edit Receipt Step 1: ...` or `Similar Category Step 1: ...` or
  `History Filter Step 1: ...` or `CI Step 1: ...`.
- One commit per step; push only when the user asks.

Setup
pip install -r requirements.txt

Run (from the repository root, so .streamlit/config.toml is used)
python -m streamlit run app.py

Run as the desktop program does (data folder, free port, opens the browser)
python desktop/launcher.py

Build the desktop program (see Desktop program)
python -m pip install -r requirements-build.txt
python -m PyInstaller desktop/ExpenseHandler.spec --noconfirm
