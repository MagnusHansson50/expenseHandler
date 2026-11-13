"""Comparing a new category name with the user's existing categories.

"mjölk" next to "Mjölk" is almost always a typo, so the UI asks before adding
it. The database still allows it: the user may choose to keep both.
"""

from typing import NamedTuple

from core.constants import FALLBACK_CATEGORY, FALLBACK_CATEGORY_LABELS, MAX_NAME_LENGTH
from core.receipt import Problem

# The fallback category's labels in every language, in comparable form. They
# are reserved (the database refuses them), so asking "add it anyway?" would
# only lead to a refusal.
_RESERVED = frozenset(" ".join(label.split()).casefold()
                      for label in (FALLBACK_CATEGORY, *FALLBACK_CATEGORY_LABELS.values()))


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


def is_reserved(name):
    """True for the fallback category's labels ("Övrigt", "Other") in any case or spacing."""
    return comparable(name) in _RESERVED


def name_problem(name):
    """Why a new category name cannot be used, as a Problem, or None if it can.

    The same rules as db.add_category (the last guard), so the UI can say
    which one was broken instead of one message for all of them.
    """
    stripped = str(name).strip()
    if not stripped:
        return Problem("category_name_empty", {})
    if len(stripped) > MAX_NAME_LENGTH:
        return Problem("category_name_too_long", {"max": MAX_NAME_LENGTH})
    if is_reserved(stripped):
        return Problem("category_name_reserved", {"name": stripped})
    return None


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
