"""Values shared by the UI, the core logic and the data layer.

Kept free of imports so any module can depend on it.
"""

# Category used when an item has no category, and that can never be removed.
FALLBACK_CATEGORY = "Other"

# Columns of the receipt being edited (and of the rows saved to history).
RECEIPT_COLUMNS = ["Item", "Price", "Category"]

# Input limits. Enforced in the UI, in core/receipt.py before saving, and
# in integrations/db.py as the last guard.
MAX_NAME_LENGTH = 50  # user and category names
MAX_ITEM_LENGTH = 100  # item descriptions
MAX_PRICE = 100_000  # kr; prices must lie within -MAX_PRICE..MAX_PRICE (discounts are negative)
