"""Accessibility checks that need no browser: colour contrast and the page language.

The colours come from the theme (THEME in desktop/launcher.py, which
tests/test_launcher.py keeps equal to config.toml) and ui/style.py. WCAG 2.1 AA:
text needs 4.5:1 against what it is on (1.4.3), the edges of controls 3:1
(1.4.11). The automated page audit (axe-core) is in tests/a11y/.
"""

import pytest

from desktop.launcher import THEME
from ui import style

from test_app import create_user, start_app

WHITE = "#FFFFFF"  # the text on primary buttons


def relative_luminance(colour):
    red, green, blue = (int(colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def linear(channel):
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def contrast(first, second):
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


SURFACES = {
    "background": THEME["backgroundColor"],
    "sand (sidebar, fields)": THEME["secondaryBackgroundColor"],
    "card": style.CARD,
    # The linen pattern's lines lie under the text on the background; axe-core
    # reports text over a background image as "incomplete", so it is checked here.
    "linen line 1": style.LINEN_COLOURS[0],
    "linen line 2": style.LINEN_COLOURS[1],
}


@pytest.mark.parametrize("surface", SURFACES)
def test_text_is_readable_on_every_surface(surface):
    assert contrast(THEME["textColor"], SURFACES[surface]) >= 4.5


@pytest.mark.parametrize("surface", ["background", "card"])
def test_the_accent_is_readable_as_text(surface):
    # Tabs, links and outlined buttons use the accent green as text colour.
    assert contrast(THEME["primaryColor"], SURFACES[surface]) >= 4.5


@pytest.mark.parametrize("surface", SURFACES)
def test_muted_text_is_readable_on_every_surface(surface):
    # The grey that replaces Streamlit's too faint secondary text (e.g. "5MB per file").
    assert contrast(style.MUTED_TEXT, SURFACES[surface]) >= 4.5


def test_text_on_primary_buttons_is_readable():
    assert contrast(WHITE, THEME["primaryColor"]) >= 4.5


@pytest.mark.parametrize("surface", SURFACES)
def test_the_edges_of_input_fields_can_be_seen(surface):
    assert THEME["showWidgetBorder"] is True
    assert contrast(THEME["borderColor"], SURFACES[surface]) >= 3


def test_contrast_is_computed_as_in_wcag():
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)


# --- The page language ------------------------------------------------------


def page_language_scripts(at):
    """The <script> setting the page language, from the title element (one per page)."""
    return [
        body[body.index("<script>"):] for body in (element.proto.body for element in at.get("html"))
        if "documentElement.lang" in body
    ]


@pytest.mark.parametrize("lang", ["sv", "en"])
def test_the_page_language_follows_the_language_selector(temp_db, lang):
    at = start_app(lang=lang)
    assert page_language_scripts(at) == [f'<script>document.documentElement.lang = "{lang}";</script>']
    create_user(at, "Anna")
    assert len(page_language_scripts(at)) == 1  # set on every page, also after logging in


def test_switching_language_changes_the_page_language(temp_db):
    at = start_app(lang="en")
    at.sidebar.selectbox(key="language").set_value("sv").run()
    assert page_language_scripts(at) == ['<script>document.documentElement.lang = "sv";</script>']


def test_only_known_languages_reach_the_script():
    with pytest.raises(ValueError):
        style.page_language_script('sv";alert(1);"')
