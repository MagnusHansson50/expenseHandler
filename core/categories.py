"""Comparing a new category name with the user's existing categories.

"mjölk" next to "Mjölk" is almost always a typo, so the UI asks before adding
it. The database still allows it: the user may choose to keep both.
"""

from typing import NamedTuple


class CategoryClash(NamedTuple):
    """An existing category that a new name collides with.

    `exact` is True when the user already has exactly that name (it cannot be
    added), False when it only differs in letter case or spacing (it can be
    added after the user confirms).
    """

    existing: str
    exact: bool


def comparable(name):
    """The form names are compared in: letter case and extra spaces ignored.

    casefold() also folds å, ä, ö and ß ("Straße" -> "strasse").
    Example: "  MJÖLK   och  ost " -> "mjölk och ost".
    """
    return " ".join(str(name).split()).casefold()


def category_clash(name, categories):
    """The existing category that `name` collides with, or None.

    An exact match (after trimming the ends, as the database stores it) wins
    over a similar one. Empty names collide with nothing.
    """
    stripped = str(name).strip()
    if not stripped:
        return None
    if stripped in categories:
        return CategoryClash(stripped, exact=True)
    wanted = comparable(stripped)
    for existing in categories:
        if comparable(existing) == wanted:
            return CategoryClash(existing, exact=False)
    return None
