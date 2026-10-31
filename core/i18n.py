"""Translations of user-facing text, and number formatting per language.

Pure Python: no Streamlit. All text the user sees is looked up here with
t(key, lang, **params); code, comments and logs stay in English.

To add a text: add the same key to every language in TRANSLATIONS, with the
same {placeholders}. tests/test_i18n.py fails if a language is missing a key
or a placeholder.
"""

import string

LANGUAGES = {"sv": "Svenska", "en": "English"}
DEFAULT_LANGUAGE = "sv"

TRANSLATIONS = {
    "sv": {
        "app_title": "🧾 ExpenseHandler",
        "language_label": "Språk",
    },
    "en": {
        "app_title": "🧾 ExpenseHandler",
        "language_label": "Language",
    },
}

# Non-breaking space: keeps "1 122,17 kr" on one line.
_NBSP = " "


def resolve_language(lang):
    """Return `lang` if it is supported, otherwise DEFAULT_LANGUAGE."""
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def t(key, lang, **params):
    """Return the text for `key` in `lang`, with {placeholders} filled from `params`.

    An unsupported language falls back to DEFAULT_LANGUAGE. An unknown key or
    a missing parameter raises KeyError: a missing text is a bug, and the
    tests check that every key used exists in every language.
    """
    text = TRANSLATIONS[resolve_language(lang)][key]
    return text.format(**params) if params else text


def placeholders(text):
    """Return the set of {placeholder} names used in a text."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def format_amount(value, lang):
    """Format an amount in kronor for display.

    Swedish: "1 122,17 kr" (space between thousands, decimal comma).
    English: "1,122.17 kr" (comma between thousands, decimal point).
    """
    rounded = round(float(value), 2)
    if rounded == 0:
        rounded = 0.0  # avoid "-0,00 kr"
    number = f"{rounded:,.2f}"  # e.g. "-1,122.17"
    if resolve_language(lang) == "sv":
        number = number.replace(",", _NBSP).replace(".", ",")
    return f"{number}{_NBSP}kr"
