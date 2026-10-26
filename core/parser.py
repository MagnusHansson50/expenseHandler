"""ICA receipt PDF parser.

An ICA item line ends with five fixed columns after the item name:

    <name> <article no> <unit price> <quantity> <st|kg> <total>
    Mjölk 3% 7310865004703 15,90 2,00 st 31,80

Discount lines follow the item they apply to and end in a negative amount:

    Rabatt: 2 för 25 -6,80

Discounts are merged into the preceding item so its price is what was actually paid.
Back-to-back lines with the same article number (e.g. the same product at two
prices) are combined into one row, since a multi-buy discount after them covers both.
"""

import io
import re

import pandas as pd
import PyPDF2

COLUMNS = ["Item", "Price"]

# Lines at or after these markers belong to the payment section, not items.
STOP_MARKERS = ("Delavstämning", "Betalat", "Betalningsinformation")

# Summary lines can end in a negative amount but are not discounts.
SKIP_PREFIXES = ("Totalt", "Summa", "Moms")

AMOUNT = r"-?\d+,\d{2}"

ITEM_LINE = re.compile(
    rf"^(?P<name>.+?)\s+(?P<article>\S+)\s+{AMOUNT}\s+\d+(?:,\d+)?\s+(?:st|kg)\s+(?P<total>{AMOUNT})$"
)
DISCOUNT_LINE = re.compile(rf"^.+\s(?P<discount>-\d+,\d{{2}})$")


def _to_float(amount):
    """Convert a Swedish-formatted amount ('15,90') to a float."""
    return float(amount.replace(",", "."))


def extract_text(file_bytes):
    """Extract the raw text of every page in a PDF."""
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_receipt_text(text):
    """Parse ICA receipt text into a DataFrame with the columns Item and Price."""
    items = []
    previous_article = None  # Article number of the line just before, if it was an item

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(marker in line for marker in STOP_MARKERS):
            break
        if line.startswith(SKIP_PREFIXES):
            continue

        item_match = ITEM_LINE.match(line)
        if item_match:
            total = _to_float(item_match["total"])
            if item_match["article"] == previous_article:
                items[-1]["Price"] = round(items[-1]["Price"] + total, 2)
            else:
                name = item_match["name"].replace("*", "").strip()
                items.append({"Item": name, "Price": total})
            previous_article = item_match["article"]
            continue

        previous_article = None
        discount_match = DISCOUNT_LINE.match(line)
        if discount_match and items:
            discounted = items[-1]["Price"] + _to_float(discount_match["discount"])
            items[-1]["Price"] = round(discounted, 2)

    return pd.DataFrame(items, columns=COLUMNS)


def parse_pdf(file_bytes):
    """Parse an uploaded ICA receipt PDF into a DataFrame with Item and Price."""
    return parse_receipt_text(extract_text(file_bytes))
