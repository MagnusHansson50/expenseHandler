"""core.categories: does a new category name collide with an existing one?"""

import pytest

from core.categories import CategoryClash, category_clash, comparable

CATEGORIES = ["Mjölk", "Frukt och grönt", "Other"]


@pytest.mark.parametrize("name", ["mjölk", "MJÖLK", "mjölk ", "  mJöLk", "MJÖLK\t"])
def test_a_name_differing_only_in_case_or_spacing_is_similar(name):
    assert category_clash(name, CATEGORIES) == CategoryClash("Mjölk", exact=False)


def test_extra_spaces_inside_the_name_are_ignored():
    assert category_clash("frukt  och   GRÖNT", CATEGORIES) == CategoryClash("Frukt och grönt", exact=False)


def test_the_same_name_is_an_exact_clash():
    assert category_clash("Mjölk", CATEGORIES) == CategoryClash("Mjölk", exact=True)
    assert category_clash("  Mjölk  ", CATEGORIES) == CategoryClash("Mjölk", exact=True)


def test_an_exact_match_wins_over_a_similar_one():
    # The user already chose to keep both; adding "mjölk" again is a plain duplicate.
    assert category_clash("mjölk", ["Mjölk", "mjölk"]) == CategoryClash("mjölk", exact=True)


@pytest.mark.parametrize("name", ["Mjölkprodukter", "Mjolk", "Frukt", "Godis", "", "   "])
def test_other_names_do_not_clash(name):
    assert category_clash(name, CATEGORIES) is None


def test_no_categories_no_clash():
    assert category_clash("Mjölk", []) is None


def test_comparable_folds_case_and_spaces():
    assert comparable("  MJÖLK   och  ost ") == "mjölk och ost"
    assert comparable("Åsa") == comparable("åsa")
    assert comparable("Straße") == comparable("STRASSE")


def test_the_result_has_named_fields():
    clash = category_clash("mjölk", CATEGORIES)
    assert clash.existing == "Mjölk" and clash.exact is False
