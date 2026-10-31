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


# --- Keys used by the UI -------------------------------------------------


def ui_keys_used_in_app():
    """Translation keys used in app.py: t("key", ...), load(..., what="key") and write_errors("key")."""
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8"))
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None)
        if name in ("t", "write_errors") and node.args and isinstance(node.args[0], ast.Constant):
            keys.add(node.args[0].value)
        if name == "t" and node.args and isinstance(node.args[0], ast.IfExp):
            keys.update(branch.value for branch in (node.args[0].body, node.args[0].orelse))
        for keyword in node.keywords:
            if name == "load" and keyword.arg == "what" and isinstance(keyword.value, ast.Constant):
                keys.add(keyword.value.value)
    return keys


def keys_produced_below_the_ui():
    """Keys created in core/receipt.py and core/auth.py (Problem("key", ...)) and db.py (class attribute key = "...")."""
    import ast
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    keys = set()
    for module in ("receipt.py", "auth.py"):
        tree = ast.parse((repo / "core" / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Problem":
                keys.add(node.args[0].value)
    db_tree = ast.parse((repo / "integrations" / "db.py").read_text(encoding="utf-8"))
    for node in ast.walk(db_tree):
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["key"]:
            if node.value.value:
                keys.add(node.value.value)
    return keys


def all_keys_in_use():
    return ui_keys_used_in_app() | keys_produced_below_the_ui()


def test_every_key_used_in_app_exists_in_every_language():
    used = all_keys_in_use()
    assert len(used) > 50  # sanity check that the scan finds the keys
    for lang, table in TRANSLATIONS.items():
        missing = used - set(table)
        assert not missing, f"{lang} is missing {sorted(missing)}"


def test_no_unused_keys():
    unused = set(TRANSLATIONS[DEFAULT_LANGUAGE]) - all_keys_in_use()
    assert not unused, f"unused translation keys: {sorted(unused)}"


def test_keys_from_core_and_db_are_found():
    assert keys_produced_below_the_ui() == {
        "problem_item_missing",
        "problem_item_too_long",
        "problem_price_missing",
        "problem_price_out_of_range",
        "user_name_empty",
        "user_name_too_long",
        "user_name_taken",
        "password_too_short",
        "password_too_long",
    }


# --- Categories ----------------------------------------------------------

from core.constants import FALLBACK_CATEGORY, FALLBACK_CATEGORY_LABELS  # noqa: E402
from core.i18n import DEFAULT_CATEGORIES, category_label, category_value  # noqa: E402


def test_fallback_label_and_default_categories_exist_for_every_language():
    assert set(FALLBACK_CATEGORY_LABELS) == set(LANGUAGES)
    assert set(DEFAULT_CATEGORIES) == set(LANGUAGES)
    assert FALLBACK_CATEGORY_LABELS["sv"] == "Övrigt"


def test_default_categories_have_the_same_length_and_no_reserved_names():
    reserved = {label.casefold() for label in FALLBACK_CATEGORY_LABELS.values()}
    lengths = {lang: len(names) for lang, names in DEFAULT_CATEGORIES.items()}
    assert len(set(lengths.values())) == 1, lengths
    for names in DEFAULT_CATEGORIES.values():
        assert len(set(names)) == len(names)
        assert not reserved & {name.casefold() for name in names}


def test_category_label_translates_only_the_fallback():
    assert category_label(FALLBACK_CATEGORY, "sv") == "Övrigt"
    assert category_label(FALLBACK_CATEGORY, "en") == "Other"
    assert category_label("Mejeri", "en") == "Mejeri"  # user data is never translated
    assert category_label("Dairy", "sv") == "Dairy"


@pytest.mark.parametrize("lang", list(LANGUAGES))
@pytest.mark.parametrize("name", [FALLBACK_CATEGORY, "Mejeri", "Dairy", "Snacks"])
def test_category_value_reverses_category_label(lang, name):
    assert category_value(category_label(name, lang), lang) == name


# --- Numbers in messages -------------------------------------------------

from core.i18n import format_number  # noqa: E402


@pytest.mark.parametrize(
    "value, swedish, english",
    [
        (5, "5", "5"),
        (100000, "100 000", "100,000"),
        (-100000, "-100 000", "-100,000"),
        (1234.5, "1 234,50", "1,234.50"),
        (50.0, "50", "50"),
    ],
)
def test_format_number_per_language(value, swedish, english):
    assert format_number(value, "sv") == swedish
    assert format_number(value, "en") == english


def test_t_formats_numeric_params_per_language():
    assert t("problem_price_out_of_range", "sv", row=3, max=100000) == (
        "Rad 3: priset måste vara mellan -100 000 och 100 000 kr."
    )
    assert t("problem_price_out_of_range", "en", row=3, max=100000) == (
        "Row 3: the price must be between -100,000 and 100,000 kr."
    )


def test_t_leaves_text_params_unchanged():
    assert t("saved_rows", "sv", count=1200, date="2026-09-26") == "1 200 rader sparades för 2026-09-26."
    assert t("user_name_taken", "en", name="1234") == "A user named '1234' already exists."
