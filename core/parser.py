"""Reading receipt PDFs.

The PDF's text is extracted with pypdf, the receipt layout is recognized and
parsed by its module in core/receipt_formats (see FORMATS), and the purchase
date, which every layout prints the same way, is read here.

The purchase date is the first YYYY-MM-DD in the text. Text extraction may glue
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

from core.receipt_formats import kivra

# The layouts that can be imported, tried in this order.
FORMATS = (kivra,)

# Used when no layout recognizes the text.
DEFAULT_FORMAT = kivra

# An ISO date not embedded in a longer number; it may be glued to letters ("Kassör2026-09-26").
ISO_DATE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")

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


def receipt_format(text):
    """Return the module in FORMATS whose layout the text is in (DEFAULT_FORMAT if none)."""
    return next((layout for layout in FORMATS if layout.matches(text)), DEFAULT_FORMAT)


def parse_receipt_date(text):
    """Return the purchase date from receipt text, or None if none is found."""
    for match in ISO_DATE.finditer(text):
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            continue  # Looked like a date but was not one, e.g. 2026-13-45
    return None


class ParsedReceipt(NamedTuple):
    """What read_receipt finds in a receipt PDF."""

    items: pd.DataFrame  # columns Item and Price
    purchase_date: date | None  # date printed on the receipt, None if not found
    paid_total: float | None  # amount paid printed on the receipt, None if not found


def read_receipt(file_bytes):
    """Parse an uploaded receipt PDF into a ParsedReceipt.

    Raises NotAPdfError or ReceiptReadError if the file cannot be read.
    """
    text = extract_text(file_bytes)
    layout = receipt_format(text)
    return ParsedReceipt(layout.parse_items(text), parse_receipt_date(text), layout.parse_paid_total(text))
