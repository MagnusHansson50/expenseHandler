"""Values shared by the UI, the core logic and the data layer.

Kept free of imports so any module can depend on it.
"""

# Category used when an item has no category, and that can never be removed.
# This internal name is what is stored in the database, in every language.
FALLBACK_CATEGORY = "Other"

# How FALLBACK_CATEGORY is shown per language. These names are reserved:
# a user cannot create a category with any of them (any letter case).
FALLBACK_CATEGORY_LABELS = {"sv": "Övrigt", "en": "Other"}

# Columns of the receipt being edited (and of the rows saved to history).
RECEIPT_COLUMNS = ["Item", "Price", "Category"]

# Input limits. Enforced in the UI, in core/receipt.py before saving, and
# in integrations/db.py as the last guard.
MAX_NAME_LENGTH = 50  # user and category names
MAX_ITEM_LENGTH = 100  # item descriptions
MAX_PRICE = 100_000  # kr; prices must lie within -MAX_PRICE..MAX_PRICE (discounts are negative)

# Password length limits. The upper limit keeps hashing a single login
# attempt cheap, so a huge "password" cannot be used to slow the server down.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
