"""Receipt copies (PDF) from Kivra.

Kivra prints every store's receipt with the same columns (ICA, Jula, Kjell & Co,
Rusta, Stadium, ...), under the header "Beskrivning Artikelnummer Pris Mängd
Summa(SEK)". An item line ends with five fixed columns after the item name:

    <name> <article no> <unit price> <quantity> <st|kg> <total>
    Mjölk 3% 7310865004703 15,90 2,00 st 31,80

A name too long for one line is printed on the line(s) above, and the columns
come alone on the last line; the name lines are joined:

    GROVDAMMSUGARE DXV20SE
    DEWALT
    033409 799,00 1,00 st 799,00

Discount lines follow the item they apply to and end in a negative amount:

    Rabatt: 2 för 25 -6,80

Discounts are merged into the preceding item so its price is what was actually paid.
So is a deposit printed below a drink without article number or unit:

    *Coca-Cola 20-p 2975805 129,00 1,00 st 133,08
    Läsk 89kr/st  -44,08
    *Pant  40,00 1 40,00

Back-to-back lines with the same article number (e.g. the same product at two
prices) are combined into one row, since a multi-buy discount after them covers both.

The total paid is read from the "Betalat" line, so callers can check that the
items add up to it.
"""

import re

import pandas as pd

from core.receipt_formats.common import COLUMNS, to_float

# Lines at or after these markers belong to the payment section, not items.
STOP_MARKERS = ("Delavstämning", "Betalat", "Betalningsinformation")

# Summary lines can end in a negative amount but are not discounts.
SKIP_PREFIXES = ("Totalt", "Summa", "Moms")

# Swedish amount with exactly two decimals and an optional minus: "15,90", "-6,80".
AMOUNT = r"-?\d+,\d{2}"

# Quantity: a whole number of pieces or a weight with decimals: "2,00", "0,85", "1".
QUANTITY = r"\d+(?:,\d+)?"

# An item line, e.g. "*Bananer Eko 2000000000001 29,90 0,85 kg 25,42".
# The name is matched lazily so the five fixed columns are taken from the end.
ITEM_LINE = re.compile(
    rf"""
    ^(?P<name>.+?)                 # item name; may contain spaces, % and a leading *
    \s+(?P<article>\S+)            # article number (used to combine repeated lines)
    \s+(?P<unit_price>{AMOUNT})    # price per piece or per kg
    \s+(?P<quantity>{QUANTITY})    # number of pieces or weight
    \s+(?P<unit>st|kg)             # unit: st = pieces, kg = kilograms
    \s+(?P<total>{AMOUNT})$        # amount for the whole line (what is parsed)
    """,
    re.VERBOSE,
)

# The columns of an item whose name did not fit: the name is on the line(s) above.
# "033409 799,00 1,00 st 799,00" after "GROVDAMMSUGARE DXV20SE" and "DEWALT".
COLUMNS_ONLY_LINE = re.compile(
    rf"""
    ^(?P<article>\S+)              # article number, first on the line
    \s+(?P<unit_price>{AMOUNT})    # price per piece or per kg
    \s+(?P<quantity>{QUANTITY})    # number of pieces or weight
    \s+(?P<unit>st|kg)             # unit: st = pieces, kg = kilograms
    \s+(?P<total>{AMOUNT})$        # amount for the whole line (what is parsed)
    """,
    re.VERBOSE,
)

# The column header above the items: "Beskrivning Artikelnummer Pris Mängd Summa(SEK)".
COLUMN_HEADER_MARKER = "Artikelnummer"

# A discount line, e.g. "Rabatt: 2 för 25 -6,80" or "Juice 2f65kr  -20,04".
# It applies to the item above it; summary lines are skipped before this is tried.
DISCOUNT_LINE = re.compile(
    r"""
    ^.+\s                          # description, separated from the amount by whitespace
    (?P<discount>-\d+,\d{2})$      # negative amount with two decimals at the end
    """,
    re.VERBOSE,
)

# A deposit line below a drink, with no article number or unit: "*Pant  40,00 1 40,00"
# (20 cans at 2 kr, counted as one) or "Pant  2,00 2 4,00". It is added to the item above.
DEPOSIT_LINE = re.compile(
    rf"""
    ^\*?Pant                       # "Pant", with ICA's leading * for an item on offer
    \s+(?P<unit_price>{AMOUNT})    # deposit per piece (or per pack)
    \s+(?P<quantity>\d+)           # number of pieces, a whole number without decimals
    \s+(?P<total>{AMOUNT})$        # deposit for the whole line (what is parsed)
    """,
    re.VERBOSE,
)

# The total paid, e.g. "Betalat 519,84" or "Betalat 5 297,00" (thousands may be grouped).
PAID_LINE = re.compile(
    r"""
    ^Betalat\s+                    # label, at the start of the (stripped) line
    (?P<amount>\d[\d\ .]*,\d{2})$  # amount; spaces or dots may group thousands
    """,
    re.VERBOSE,
)


def matches(text):
    """True if the text has Kivra's column header above the items."""
    return any(COLUMN_HEADER_MARKER in line for line in text.splitlines())


def parse_items(text):
    """Parse receipt text into a DataFrame with the columns Item and Price."""
    items = []
    previous_article = None  # Article number of the line just before, if it was an item
    name_lines = []  # Unmatched lines since the last item: the name of a wrapped item

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(marker in line for marker in STOP_MARKERS):
            break
        if line.startswith(SKIP_PREFIXES):
            continue
        if COLUMN_HEADER_MARKER in line:
            name_lines = []  # store address and other header lines are never part of a name
            continue

        item_match = ITEM_LINE.match(line)
        columns_match = None if item_match else COLUMNS_ONLY_LINE.match(line)
        if item_match or columns_match:
            match = item_match or columns_match
            if item_match:
                name = item_match["name"]
            else:
                # Fall back to the article number so the amount is never lost.
                name = " ".join(name_lines) or columns_match["article"]
            name_lines = []
            total = to_float(match["total"])
            if match["article"] == previous_article:
                items[-1]["Price"] = round(items[-1]["Price"] + total, 2)
            else:
                items.append({"Item": name.replace("*", "").strip(), "Price": total})
            previous_article = match["article"]
            continue

        deposit_match = DEPOSIT_LINE.match(line)
        if deposit_match:
            previous_article = None
            name_lines = []
            deposit = to_float(deposit_match["total"])
            if items:
                items[-1]["Price"] = round(items[-1]["Price"] + deposit, 2)
            else:
                items.append({"Item": "Pant", "Price": deposit})  # never lose an amount
            continue

        discount_match = DISCOUNT_LINE.match(line)
        if discount_match:
            previous_article = None  # a discount ends a run of the same article
            name_lines = []
            if items:
                discounted = items[-1]["Price"] + to_float(discount_match["discount"])
                items[-1]["Price"] = round(discounted, 2)
            continue

        name_lines.append(line)

    return pd.DataFrame(items, columns=COLUMNS)


def parse_paid_total(text):
    """Return the "Betalat" amount from receipt text, or None if there is none."""
    for line in text.splitlines():
        match = PAID_LINE.match(line.strip())
        if match:
            return to_float(re.sub(r"[ .]", "", match["amount"]))
    return None
