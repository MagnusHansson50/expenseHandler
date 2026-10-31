import os
import re
from datetime import date
from pathlib import Path

import pytest

import core.parser
from core.parser import (
    NotAPdfError,
    ParsedReceipt,
    ReceiptReadError,
    parse_receipt_date,
    parse_receipt_text,
    read_receipt,
)

# Mirrors the item layout extracted from a real ICA receipt.
SAMPLE_RECEIPT = """ICA Supermarket Testbutiken
Kassör2026-10-20
08:27
Beskrivning Artikelnummer Pris Mängd Summa(SEK)
Mjölk 3% 7310865004703 15,90 2,00 st 31,80
Rabatt: 2 för 25 -6,80
*Bananer Eko 2000000000001 29,90 0,85 kg 25,42
*Super crunch prem 2033432 26,45 4,00 st 105,80
*Super crunch prem 2033432 14,92 2,00 st 52,90
Fryst potati 2f45kr  -7,90
Fryst potat 6f100kr  -50,80

Pant 1 7300000000003 1,00 1,00 st 1,00
Totalt 3 rader -2,00
          Delavstämning korrekt
 Betalat 151,42
Kaffe 7300000000004 59,90 1,00 st 59,90
2026-10-21 08:26     AID:A0000000041010
"""


def make_pdf(text):
    """Build a minimal one-page PDF with one text line per row of `text`."""
    ops = ["BT /F1 10 Tf 40 800 Td 12 TL"]
    for line in text.splitlines():
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({escaped}) Tj T*")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return pdf


# --- Items ---------------------------------------------------------------


def test_parse_receipt_text_items_and_prices():
    items = parse_receipt_text(SAMPLE_RECEIPT)
    assert list(items.columns) == ["Item", "Price"]
    assert items["Item"].tolist() == ["Mjölk 3%", "Bananer Eko", "Super crunch prem", "Pant 1"]
    assert items["Price"].tolist() == [25.0, 25.42, 100.0, 1.0]


def test_discount_is_merged_into_previous_item():
    items = parse_receipt_text("Feta 1402453 21,46 2,00 st 42,92\nFeta 2f35kr  -7,92")
    assert items["Price"].tolist() == [35.0]


def test_same_article_on_consecutive_lines_is_combined():
    items = parse_receipt_text(
        "*Super crunch prem 2033432 26,45 4,00 st 105,80\n"
        "*Super crunch prem 2033432 14,92 2,00 st 52,90\n"
        "Fryst potat 6f100kr  -58,70"
    )
    assert items.to_dict("records") == [{"Item": "Super crunch prem", "Price": 100.0}]


def test_summary_lines_are_not_treated_as_discounts():
    items = parse_receipt_text("Pant 1 7300000000003 1,00 1,00 st 1,00\nTotalt 3 rader -2,00")
    assert items["Price"].tolist() == [1.0]


def test_parsing_stops_at_payment_section():
    items = parse_receipt_text(SAMPLE_RECEIPT)
    assert "Kaffe" not in items["Item"].tolist()


def test_no_items_gives_empty_frame_with_columns():
    items = parse_receipt_text("Nothing here\nRabatt -5,00")
    assert items.empty
    assert list(items.columns) == ["Item", "Price"]


# --- Date ----------------------------------------------------------------


def test_receipt_date_is_found_even_when_glued_to_label():
    assert parse_receipt_date(SAMPLE_RECEIPT) == date(2026, 10, 20)


def test_receipt_date_skips_invalid_and_embedded_numbers():
    text = "Ref 12026-09-26x\nBad 2026-13-45\nKassör2026-01-02"
    assert parse_receipt_date(text) == date(2026, 1, 2)


def test_receipt_without_date_returns_none():
    assert parse_receipt_date("No date on this receipt") is None


# --- PDF -----------------------------------------------------------------


def test_read_receipt_from_pdf_matches_text_parsing():
    items, purchase_date = read_receipt(make_pdf(SAMPLE_RECEIPT))
    assert items.equals(parse_receipt_text(SAMPLE_RECEIPT))
    assert purchase_date == date(2026, 10, 20)


def test_read_receipt_returns_named_fields():
    parsed = read_receipt(make_pdf(SAMPLE_RECEIPT))
    assert isinstance(parsed, ParsedReceipt)
    assert parsed.items.equals(parse_receipt_text(SAMPLE_RECEIPT))
    assert parsed.purchase_date == date(2026, 10, 20)


@pytest.mark.parametrize(
    "data",
    [b"", b"Hello, this is text", b"\x89PNG\r\n\x1a\n", b"PK\x03\x04 zip", b" %PDF-1.4 leading space"],
)
def test_non_pdf_bytes_are_rejected_before_parsing(data):
    with pytest.raises(NotAPdfError):
        read_receipt(data)


def test_broken_pdf_raises_receipt_read_error_with_cause():
    with pytest.raises(ReceiptReadError) as caught:
        read_receipt(b"%PDF-1.4\nthis is not a real PDF body")
    assert caught.value.__cause__ is not None  # pypdf's own error is kept for logging


def test_bug_in_our_parsing_is_not_hidden_as_a_read_error(monkeypatch):
    def broken_parser(_text):
        raise KeyError("simulated bug in parse_receipt_text")

    monkeypatch.setattr(core.parser, "parse_receipt_text", broken_parser)
    with pytest.raises(KeyError):
        read_receipt(make_pdf(SAMPLE_RECEIPT))


def test_broad_except_is_only_used_at_the_pypdf_boundary():
    repo = Path(__file__).resolve().parent.parent
    sources = [repo / "app.py", *repo.glob("core/*.py"), *repo.glob("integrations/*.py")]
    found = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8").count("except Exception")
        for path in sources
    }
    assert {name: count for name, count in found.items() if count} == {"core/parser.py": 1}


def test_unmaintained_pypdf2_is_not_imported():
    repo = Path(__file__).resolve().parent.parent
    imports_pypdf2 = re.compile(r"^\s*(import|from)\s+PyPDF2\b", re.MULTILINE)
    for path in [repo / "app.py", *repo.glob("core/*.py"), *repo.glob("integrations/*.py")]:
        assert not imports_pypdf2.search(path.read_text(encoding="utf-8")), path.name


# Real receipts contain personal data and are never committed. To run this test,
# point ICA_SAMPLE_PDF at a local receipt; set ICA_SAMPLE_TOTAL (e.g. "1122.17")
# to also check the parsed sum against the receipt's "Betalat" amount.
@pytest.mark.skipif(not os.environ.get("ICA_SAMPLE_PDF"), reason="ICA_SAMPLE_PDF not set")
def test_real_ica_receipt():
    items, purchase_date = read_receipt(Path(os.environ["ICA_SAMPLE_PDF"]).read_bytes())
    assert not items.empty
    assert items["Item"].str.len().gt(0).all()
    assert purchase_date is not None

    expected_total = os.environ.get("ICA_SAMPLE_TOTAL")
    if expected_total:
        assert round(items["Price"].sum(), 2) == float(expected_total)
