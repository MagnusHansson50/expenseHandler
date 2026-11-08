"""The Kivra layout (core/receipt_formats/kivra.py)."""

import pytest

from core.receipt_formats import kivra
from core.receipt_formats.kivra import parse_items, parse_paid_total
from test_parser import SAMPLE_RECEIPT, WRAPPED_RECEIPT


def test_kivra_is_recognized_by_its_column_header():
    assert kivra.matches(SAMPLE_RECEIPT)
    assert kivra.matches(WRAPPED_RECEIPT)
    assert not kivra.matches("VEGOSKIVOR ORIGINAL  21,90\n Totalt 21,90 SEK")


# --- Items ---------------------------------------------------------------


def test_items_and_prices():
    items = parse_items(SAMPLE_RECEIPT)
    assert list(items.columns) == ["Item", "Price"]
    assert items["Item"].tolist() == ["Mjölk 3%", "Bananer Eko", "Super crunch prem", "Pant 1"]
    assert items["Price"].tolist() == [25.0, 25.42, 100.0, 1.0]


def test_discount_is_merged_into_previous_item():
    items = parse_items("Feta 1402453 21,46 2,00 st 42,92\nFeta 2f35kr  -7,92")
    assert items["Price"].tolist() == [35.0]


def test_deposit_without_article_number_is_added_to_the_drink_above():
    # Mirrors ICA's layout: the deposit line has no article number and no unit.
    items = parse_items(
        "*Läsk 20-p 2975805 129,00 1,00 st 133,08\n"
        "Läsk 89kr/st  -44,08\n"
        "*Pant  40,00 1 40,00\n"
        "Kex 1026236 12,32 1,00 st 12,32\n"
        "Cider 2563365 18,56 2,00 st 33,12\n"
        "Pant  2,00 2 4,00"
    )
    assert items.to_dict("records") == [
        {"Item": "Läsk 20-p", "Price": 129.0},  # 133,08 - 44,08 + 40,00
        {"Item": "Kex", "Price": 12.32},
        {"Item": "Cider", "Price": 37.12},  # 33,12 + 4,00
    ]


def test_deposit_with_no_item_above_is_kept():
    assert parse_items("Pant  2,00 2 4,00").to_dict("records") == [{"Item": "Pant", "Price": 4.0}]


def test_same_article_on_consecutive_lines_is_combined():
    items = parse_items(
        "*Super crunch prem 2033432 26,45 4,00 st 105,80\n"
        "*Super crunch prem 2033432 14,92 2,00 st 52,90\n"
        "Fryst potat 6f100kr  -58,70"
    )
    assert items.to_dict("records") == [{"Item": "Super crunch prem", "Price": 100.0}]


def test_summary_lines_are_not_treated_as_discounts():
    items = parse_items("Pant 1 7300000000003 1,00 1,00 st 1,00\nTotalt 3 rader -2,00")
    assert items["Price"].tolist() == [1.0]


def test_parsing_stops_at_payment_section():
    items = parse_items(SAMPLE_RECEIPT)
    assert "Kaffe" not in items["Item"].tolist()


def test_name_on_lines_above_the_columns_is_joined():
    items = parse_items(WRAPPED_RECEIPT)
    assert items["Item"].tolist() == [
        "Laddare 65W",
        "Kabel USB-C 2m, vit - flätad, upp till 60W",
        "ARBETSBÄNK 120CM",
        "GROVDAMMSUGARE DXV20SE DEWALT",
    ]


def test_discount_after_a_wrapped_item_applies_to_that_item():
    items = parse_items(WRAPPED_RECEIPT)
    assert items["Price"].tolist() == [319.92, 199.92, 1999.0, 799.0]
    assert round(items["Price"].sum(), 2) == 3317.84


def test_header_lines_are_not_used_as_an_item_name():
    items = parse_items(
        "Testbutiken\nStorgatan 1\nBeskrivning Artikelnummer Pris Mängd Summa(SEK)\n"
        "LÅNG VARA\n033409 799,00 1,00 st 799,00"
    )
    assert items["Item"].tolist() == ["LÅNG VARA"]


def test_columns_without_any_name_keep_the_amount():
    items = parse_items("Rabatt  -5,00\n033409 799,00 1,00 st 799,00")
    assert items.to_dict("records") == [{"Item": "033409", "Price": 799.0}]


def test_wrapped_items_with_the_same_article_are_combined():
    items = parse_items(
        "Choklad Kexchoklad\n8x60 g\n991616650101 53,90 1,00 st 53,90\n"
        "Choklad Kexchoklad\n8x60 g\n991616650101 53,90 1,00 st 53,90"
    )
    assert items.to_dict("records") == [{"Item": "Choklad Kexchoklad 8x60 g", "Price": 107.8}]


def test_no_items_gives_empty_frame_with_columns():
    items = parse_items("Nothing here\nRabatt -5,00")
    assert items.empty
    assert list(items.columns) == ["Item", "Price"]


# --- Total paid ----------------------------------------------------------


def test_paid_total_is_read_and_matches_the_items():
    assert parse_paid_total(SAMPLE_RECEIPT) == 151.42
    assert round(parse_items(SAMPLE_RECEIPT)["Price"].sum(), 2) == 151.42
    assert parse_paid_total(WRAPPED_RECEIPT) == 3317.84


@pytest.mark.parametrize("line", [" Betalat 5297,00", "Betalat 5 297,00", "Betalat 5.297,00"])
def test_paid_total_with_grouped_thousands(line):
    assert parse_paid_total(f"Moms 25,00\n{line}\nKort 5297,00") == 5297.0


@pytest.mark.parametrize(
    "text",
    ["No total here", "Betalat", "Betalat kort", "Ej betalat 10,00", "Betalat -5,00", "Totalt: SEK 519,84"],
)
def test_receipt_without_paid_total_returns_none(text):
    assert parse_paid_total(text) is None
