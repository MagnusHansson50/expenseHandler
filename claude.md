Project
Streamlit web application for splitting grocery receipts (specifically from ICA). 
The app will parse PDF receipts, allow manual item entry, categorize purchases, 
calculate individual and shared costs, and save history to a database.

Tech stack
- Python 3.12+
- Streamlit (for Web UI and state management)
- Pandas (for Data manipulation and tables)
- PyPDF2 (for PDF text extraction)
- SQLite3 (for Local persistent database)

Code conventions
- Naming: `snake_case` for functions and variables.
- Modularization: Database operations (init, save, load, delete) should be separated into distinct functions.
- Language: UI text, variables or comments in English.

Architecture
- The application will follow a single-file structure (`app.py`).
- State Management: The app must heavily rely on Streamlit's `st.session_state` to prevent UI freezing and data loss during reactive re-renders (especially for editable data tables).
- Data Storage: Will use a local SQLite database (`kvitto_minne.db`) for persistent storage of categories, item-to-category mappings, and historical receipts.
- Connection Handling: SQLite connections must use `check_same_thread=False` to prevent locking issues within Streamlit's threading model.
- PDF Parsing: Will use a combination of text splitting and Regex to identify items, prices, quantities, and discounts specific to ICA's PDF format.

Rules
- Do not break Streamlit's reactive loop. Always use `st.form` or `st.session_state` for UI elements that trigger heavy updates to prevent infinite reloads.
- Design the PDF parsing logic specifically for the ICA receipt format.
- Keep the planned `kvitto_minne.db` schema stable. Always use `IF NOT EXISTS` for table creation.
- All file operations involving uploaded PDFs must use `io.BytesIO` to prevent Streamlit from losing the file context upon reload.

Project structure (Planned)
/
├── CLAUDE.md
├── app.py              # Main Streamlit application and business logic (To be built)
├── requirements.txt    # Project dependencies
└── kvitto_minne.db     # SQLite database (Will be auto-generated on first run)

Setup
pip install -r requirements.txt
# Alternatively: pip install streamlit pandas PyPDF2

Run
python -m streamlit run app.py