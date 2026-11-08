"""Digital receipts (PDF) from Willys.

The PDF is a copy of the till receipt, one line of fixed-width text per row.
The items come first, each with its amount at the end; several of the same
item show the quantity and unit price before it:

    VEGOSKIVOR ORIGINAL                  21,90
    CHOKLADKAKA MJÖLK     4st*23,90      95,60

Indented lines below an item belong to it: discounts (negative) and deposits
("pant", positive). They are merged into the item above so its price is what
was actually paid:

    FANTA ORANGE 6P                      40,60
      Rabatt:DRYCK                       -4,18
      +PANT ALUMINIUMBURK 1KR             6,00

A multi-buy discount can cover several items above it and be larger than the
last one; it then becomes a row of its own, so no item gets a negative price:

    CHOKLADKAKA DAIM                     23,90
      Willys Plus:CHOKLAD               -34,50

The items end at "Totalt N varor"; the next line, "Totalt 206,60 SEK", is the
amount paid. Store, separator ("-----", "=== Start Självscanning ===") and
payment lines carry no amount at the end of an item-like line, or come after
the items, and are skipped.

The layout is recognized by those two total lines. Only receipts from the
self-checkout have been seen; a weighed item printed as its name on one line
and the weight and amount on the next is read as one item, but has not been
seen on a real receipt.
"""

import re

import pandas as pd

from core.receipt_formats.common import COLUMNS, to_float

# Swedish amount with exactly two decimals and an optional minus: "21,90", "-34,50".
AMOUNT = r"-?\d+,\d{2}"

# A line with an amount at the end: an item, or (indented) a discount or deposit.
# "CHOKLADKAKA MJÖLK     4st*23,90      95,60", "  Rabatt:DRYCK   -4,18".
AMOUNT_LINE = re.compile(
    rf"""
    ^(?P<indent>\s*)                    # leading spaces: an indented line belongs to the item above
    (?P<text>\S.*?)                     # item name or description
    (?:\s+\d+st\*\d+,\d{{2}})?          # optional quantity and unit price: "4st*23,90"
    \s+(?P<amount>{AMOUNT})$            # amount for the whole line (what is parsed)
    """,
    re.VERBOSE,
)

# The end of the items: "Totalt 9 varor".
ITEM_COUNT_LINE = re.compile(
    r"""
    ^\s*Totalt\s+\d+\s+varor\s*$        # "Totalt", the number of items, "varor"
    """,
    re.VERBOSE,
)

# The amount paid: "Totalt    206,60 SEK" (thousands may be grouped: "1 234,50").
PAID_LINE = re.compile(
    r"""
    ^\s*Totalt\s+                       # label
    (?P<amount>\d[\d\ ]*,\d{2})         # amount; spaces may group thousands
    \s+SEK\s*$                          # currency
    """,
    re.VERBOSE,
)

# Separator lines: "------", "=====", "========== Start Självscanning ===========".
SEPARATOR_LINE = re.compile(r"^\s*[-=]{3,}")


def matches(text):
    """True if the text has Willys' two total lines ("Totalt 9 varor", "Totalt 206,60 SEK")."""
    lines = text.splitlines()
    return any(ITEM_COUNT_LINE.match(line) for line in lines) and any(PAID_LINE.match(line) for line in lines)


def _belongs_to_item_above(match):
    """An indented line, a deposit ("+PANT ...") or a discount (negative amount)."""
    return bool(match["indent"]) or match["text"].startswith("+") or match["amount"].startswith("-")


def parse_items(text):
    """Parse receipt text into a DataFrame with the columns Item and Price."""
    items = []
    name_line = None  # a line without an amount just before: the name of a weighed item

    for line in text.splitlines():
        if ITEM_COUNT_LINE.match(line):
            break  # the items end here
        if not line.strip() or SEPARATOR_LINE.match(line):
            name_line = None
            continue

        match = AMOUNT_LINE.match(line)
        if not match:
            name_line = line.strip()  # store header, or a name whose amount is on the next line
            continue

        amount = to_float(match["amount"])
        text_part = match["text"].strip()
        if name_line is not None and match["indent"] and amount >= 0:
            items.append({"Item": name_line, "Price": amount})  # "BANANER" / "  0,856kg*... 18,75"
        elif _belongs_to_item_above(match) and items and items[-1]["Price"] + amount >= 0:
            items[-1]["Price"] = round(items[-1]["Price"] + amount, 2)
        else:
            # An item, or a discount larger than the item above (it covers several).
            items.append({"Item": text_part, "Price": amount})
        name_line = None

    return pd.DataFrame(items, columns=COLUMNS)


def parse_paid_total(text):
    """Return the "Totalt ... SEK" amount from receipt text, or None if there is none."""
    for line in text.splitlines():
        match = PAID_LINE.match(line)
        if match:
            return to_float(match["amount"].replace(" ", ""))
    return None
