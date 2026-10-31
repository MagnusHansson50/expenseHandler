"""ICA receipt PDF parser.

An ICA item line ends with five fixed columns after the item name:

    <name> <article no> <unit price> <quantity> <st|kg> <total>
    Mjölk 3% 7310865004703 15,90 2,00 st 31,80

Discount lines follow the item they apply to and end in a negative amount:

    Rabatt: 2 för 25 -6,80

Discounts are merged into the preceding item so its price is what was actually paid.
Back-to-back lines with the same article number (e.g. the same product at two
prices) are combined into one row, since a multi-buy discount after them covers both.

The purchase date is the first YYYY-MM-DD in the header. Text extraction may glue
it to the preceding label (e.g. "Kassör2026-09-26"), so it is not matched on word
boundaries.

PDFs are read with pypdf (PyPDF2 is unmaintained and has unpatched denial-of-service
bugs). Uploads that do not start with the PDF header are rejected before parsing.
"""

import io
import re
from datetime import date
from typing import NamedTuple

import pandas as pd
from pypdf import PdfReader

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
ISO_DATE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")


def _to_float(amount):
    """Convert a Swedish-formatted amount ('15,90') to a float."""
    return float(amount.replace(",", "."))


PDF_HEADER = b"%PDF-"


class NotAPdfError(ValueError):
    """Raised when uploaded bytes are not a PDF file."""


class ReceiptReadError(Exception):
    """Raised when pypdf cannot read a file that looks like a PDF.

    The original pypdf exception is kept as __cause__ for logging.
    """


def extract_text(file_bytes):
    """Extract the raw text of every page in a PDF.

    Raises NotAPdfError if the bytes do not start with the PDF header, and
    ReceiptReadError if pypdf fails to read them.
    """
    if not file_bytes.startswith(PDF_HEADER):
        raise NotAPdfError("The file is not a PDF.")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as error:
        # Boundary to an external library: broken or hostile PDFs make pypdf
        # raise many unrelated exception types. Only pypdf calls are inside
        # this try; errors in our own parsing must not be hidden here.
        raise ReceiptReadError("Could not read the PDF.") from error
    return "\n".join(pages)


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


def parse_receipt_date(text):
    """Return the purchase date from ICA receipt text, or None if none is found."""
    for match in ISO_DATE.finditer(text):
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            continue  # Looked like a date but was not one, e.g. 2026-13-45
    return None


class ParsedReceipt(NamedTuple):
    """What read_receipt finds in an ICA receipt PDF."""

    items: pd.DataFrame  # columns Item and Price
    purchase_date: date | None  # date printed on the receipt, None if not found


def read_receipt(file_bytes):
    """Parse an uploaded ICA receipt PDF into a ParsedReceipt.

    Raises NotAPdfError or ReceiptReadError if the file cannot be read.
    """
    text = extract_text(file_bytes)
    return ParsedReceipt(parse_receipt_text(text), parse_receipt_date(text))
