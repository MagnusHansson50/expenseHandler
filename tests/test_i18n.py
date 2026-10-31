import pytest

from core.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    TRANSLATIONS,
    format_amount,
    placeholders,
    resolve_language,
    t,
)

NBSP = " "


# --- Translation tables --------------------------------------------------


def test_every_language_has_a_table_and_the_default_is_supported():
    assert set(TRANSLATIONS) == set(LANGUAGES)
    assert DEFAULT_LANGUAGE == "sv"
    assert DEFAULT_LANGUAGE in LANGUAGES


def test_all_languages_have_the_same_keys():
    reference = set(TRANSLATIONS[DEFAULT_LANGUAGE])
    for lang, table in TRANSLATIONS.items():
        assert set(table) == reference, f"{lang}: missing {reference - set(table)}, extra {set(table) - reference}"


def test_all_languages_use_the_same_placeholders():
    for key, reference_text in TRANSLATIONS[DEFAULT_LANGUAGE].items():
        for lang, table in TRANSLATIONS.items():
            assert placeholders(table[key]) == placeholders(reference_text), (lang, key)


def test_no_text_is_empty():
    for lang, table in TRANSLATIONS.items():
        for key, text in table.items():
            assert text.strip(), (lang, key)


# --- t() -----------------------------------------------------------------


def test_t_returns_text_in_the_requested_language():
    assert t("language_label", "sv") == "Språk"
    assert t("language_label", "en") == "Language"


def test_unknown_language_falls_back_to_default():
    assert resolve_language("de") == DEFAULT_LANGUAGE
    assert resolve_language(None) == DEFAULT_LANGUAGE
    assert t("language_label", "de") == t("language_label", DEFAULT_LANGUAGE)


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        t("no_such_key", "sv")


def test_placeholders_are_filled_and_missing_ones_raise(monkeypatch):
    monkeypatch.setitem(TRANSLATIONS["sv"], "greeting", "Hej {name}, du har {count} kvitton")
    assert t("greeting", "sv", name="Anna", count=3) == "Hej Anna, du har 3 kvitton"
    with pytest.raises(KeyError):
        t("greeting", "sv", name="Anna")


def test_text_with_braces_but_no_params_is_returned_unchanged(monkeypatch):
    monkeypatch.setitem(TRANSLATIONS["en"], "literal", "Use {name} later")
    assert t("literal", "en") == "Use {name} later"


# --- format_amount -------------------------------------------------------


@pytest.mark.parametrize(
    "value, swedish, english",
    [
        (1122.17, f"1{NBSP}122,17{NBSP}kr", f"1,122.17{NBSP}kr"),
        (45, f"45,00{NBSP}kr", f"45.00{NBSP}kr"),
        (-6.8, f"-6,80{NBSP}kr", f"-6.80{NBSP}kr"),
        (1234567.891, f"1{NBSP}234{NBSP}567,89{NBSP}kr", f"1,234,567.89{NBSP}kr"),
        (0.1 + 0.2, f"0,30{NBSP}kr", f"0.30{NBSP}kr"),
        (-0.001, f"0,00{NBSP}kr", f"0.00{NBSP}kr"),
    ],
)
def test_format_amount_per_language(value, swedish, english):
    assert format_amount(value, "sv") == swedish
    assert format_amount(value, "en") == english


def test_format_amount_unknown_language_uses_default():
    assert format_amount(10, "xx") == format_amount(10, DEFAULT_LANGUAGE)
