"""core.categories: does a new category name collide with an existing one?"""

import pytest

from core.categories import CategoryClash, category_clash, comparable, is_reserved, name_problem

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


@pytest.mark.parametrize("name", ["Other", "other", "ÖVRIGT", " övrigt ", "Övrigt"])
def test_the_fallback_labels_are_reserved(name):
    assert is_reserved(name)


@pytest.mark.parametrize("name", ["Others", "Övriga", "Mjölk", ""])
def test_other_names_are_not_reserved(name):
    assert not is_reserved(name)


# --- Why a new name is refused ----------------------------------------------------


@pytest.mark.parametrize(
    "name, key",
    [("", "category_name_empty"), ("   ", "category_name_empty"),
     ("x" * 51, "category_name_too_long"), ("Övrigt", "category_name_reserved"), (" other ", "category_name_reserved")],
)
def test_name_problem_says_why(name, key):
    assert name_problem(name).key == key


def test_name_problem_gives_the_limit_and_the_reserved_name():
    assert name_problem("x" * 51).params == {"max": 50}
    assert name_problem(" Övrigt ").params == {"name": "Övrigt"}


@pytest.mark.parametrize("name", ["Mjölk", "x" * 50, "Övriga", " Godis "])
def test_allowed_names_have_no_problem(name):
    assert name_problem(name) is None
