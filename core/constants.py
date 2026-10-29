"""Values shared by the UI, the core logic and the data layer.

Kept free of imports so any module can depend on it.
"""

# Category used when an item has no category, and that can never be removed.
FALLBACK_CATEGORY = "Other"

# Columns of the receipt being edited (and of the rows saved to history).
RECEIPT_COLUMNS = ["Item", "Price", "Category"]
