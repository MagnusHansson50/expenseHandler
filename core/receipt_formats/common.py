"""Helpers shared by the receipt layouts."""

# The columns every layout's parse_items() returns.
COLUMNS = ["Item", "Price"]


def to_float(amount):
    """Convert a Swedish-formatted amount ('15,90', '-6,80') to a float."""
    return float(amount.replace(",", "."))
