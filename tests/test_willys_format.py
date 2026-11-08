"""The Willys layout (core/receipt_formats/willys.py).

The samples mirror the layout of real self-checkout receipts with a made-up
store and no card or member numbers. Real receipts are never committed.
"""

from datetime import date

import pytest

from core.parser import read_receipt, receipt_format
from core.receipt_formats import kivra, willys
from core.receipt_formats.willys import parse_items, parse_paid_total
from test_parser import SAMPLE_RECEIPT, make_pdf

WILLYS_RECEIPT = """            TESTBUTIKEN STORGATAN
          TELEFON: 000-000 000
             Org: 000000-0000
------------------------------------------
========== Start Självscanning ===========
FANTA ORANGE 6P                      40,60
  Rabatt:DRYCK                       -4,18
  +PANT ALUMINIUMBURK 1KR             6,00
NÖTMIX175G HONU/S     2st*27,35      54,70
  2 * Rabatt:NÖTMIX                  -7,72
CHOKLADKAKA MJÖLK     4st*23,90      95,60
CHOKLADKAKA DAIM                     23,90
  Willys Plus:CHOKLAD               -34,50
MELON VATTEN                         65,27
========== Slut Självscanning  ===========
------------------------------------------
  Totalt 9 varor
 Totalt    239,67 SEK
==========================================
Med Willys Plus har du sparat:       34,50
==========================================
Mottaget  Kontokort                 239,67
KÖP                             239.67 SEK
2026-11-05 08:16:28              TSI: E800
 Moms%      Moms          Netto     Brutto
 6,00      13,57         226,10     239,67
Kassa: 1/1               2026-11-05  08:16
"""


def records(text):
    return parse_items(text).to_dict("records")


# --- Recognizing the layout ------------------------------------------------


def test_willys_is_recognized_by_its_total_lines():
    assert willys.matches(WILLYS_RECEIPT)
    assert receipt_format(WILLYS_RECEIPT) is willys


def test_kivra_is_not_taken_for_willys():
    assert not willys.matches(SAMPLE_RECEIPT)
    assert receipt_format(SAMPLE_RECEIPT) is kivra


def test_one_total_line_is_not_enough():
    assert not willys.matches("  Totalt 3 varor\nBetalat 10,00")
    assert not willys.matches(" Totalt    10,00 SEK")


# --- Items -----------------------------------------------------------------


def test_items_discounts_and_deposits():
    assert records(WILLYS_RECEIPT) == [
        {"Item": "FANTA ORANGE 6P", "Price": 42.42},  # 40,60 - 4,18 + 6,00
        {"Item": "NÖTMIX175G HONU/S", "Price": 46.98},  # 54,70 - 7,72
        {"Item": "CHOKLADKAKA MJÖLK", "Price": 95.6},  # quantity and unit price are not in the name
        {"Item": "CHOKLADKAKA DAIM", "Price": 23.9},
        {"Item": "Willys Plus:CHOKLAD", "Price": -34.5},  # larger than the item above: its own row
        {"Item": "MELON VATTEN", "Price": 65.27},
    ]


def test_items_add_up_to_the_amount_paid():
    assert parse_paid_total(WILLYS_RECEIPT) == 239.67
    assert round(parse_items(WILLYS_RECEIPT)["Price"].sum(), 2) == 239.67


def test_header_separators_and_payment_lines_are_not_items():
    names = parse_items(WILLYS_RECEIPT)["Item"].tolist()
    assert not any("TESTBUTIKEN" in name or "Mottaget" in name or "sparat" in name for name in names)


def test_a_discount_smaller_than_the_item_is_merged():
    assert records("SMÖR                                 50,00\n  Willys Plus:SMÖR  -10,00") == [
        {"Item": "SMÖR", "Price": 40.0}
    ]


def test_discount_and_deposit_are_merged_without_indentation():
    # Text extraction may drop leading spaces; signs still tell them apart.
    assert records("FANTA 6P  40,60\nRabatt:DRYCK  -4,18\n+PANT 1KR  6,00") == [
        {"Item": "FANTA 6P", "Price": 42.42}
    ]


def test_a_discount_with_no_item_above_is_its_own_row():
    assert records("  Rabatt:DRYCK  -4,18") == [{"Item": "Rabatt:DRYCK", "Price": -4.18}]


def test_a_weighed_item_with_its_amount_on_the_next_line():
    assert records("BANANER\n  0,856kg*21,90kr/kg      18,75\nMJÖLK  15,90") == [
        {"Item": "BANANER", "Price": 18.75},
        {"Item": "MJÖLK", "Price": 15.9},
    ]


def test_no_items_gives_empty_frame_with_columns():
    items = parse_items("------\n  Totalt 0 varor\n Totalt 0,00 SEK")
    assert items.empty
    assert list(items.columns) == ["Item", "Price"]


# --- Amount paid -----------------------------------------------------------


@pytest.mark.parametrize("line", [" Totalt    1234,50 SEK", " Totalt 1 234,50 SEK"])
def test_paid_total_with_grouped_thousands(line):
    assert parse_paid_total(f"  Totalt 3 varor\n{line}") == 1234.5


@pytest.mark.parametrize("text", ["No total", "  Totalt 3 varor", "Totalt 12,00", "Totalt -5,00 SEK"])
def test_receipt_without_paid_total_returns_none(text):
    assert parse_paid_total(text) is None


# --- PDF -------------------------------------------------------------------


def test_read_receipt_from_a_willys_pdf():
    parsed = read_receipt(make_pdf(WILLYS_RECEIPT))
    assert parsed.items.equals(parse_items(WILLYS_RECEIPT))
    assert parsed.purchase_date == date(2026, 11, 5)
    assert parsed.paid_total == 239.67
