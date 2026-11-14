"""The app can be used with the keyboard only (WCAG 2.1.1): no mouse in these tests.

A new user registers, adds an item, gives it a category in the review popup,
saves the receipt, switches to History and opens Settings, all with Tab,
Shift+Tab, the arrow keys, Enter and typing. Every step must be reachable
within a bounded number of Tab presses, so a control that cannot be focused
fails the test. What is known not to work well: after an action Streamlit
redraws the page and focus moves back to the top (see README).
"""

import pytest
from a11y_helpers import TEST_PASSWORD, open_app, settle

FOCUSED = """() => {
  const element = document.activeElement;
  if (!element || element === document.body) return "";
  const name = element.getAttribute("aria-label") || element.innerText || element.value || "";
  return `${element.tagName.toLowerCase()}|${element.getAttribute("role") || ""}|${name.replace(/\\s+/g, " ").trim()}`;
}"""


def focused(page):
    return page.evaluate(FOCUSED)


def tab_to(page, text, limit=60, backwards=False, role=None):
    """Press Tab (or Shift+Tab) until the focused element mentions `text`; fail if it never does.

    The <main> region also takes focus (the skip link's target) and contains all
    the page's text, so it never counts as a match.
    """
    for _ in range(limit):
        page.keyboard.press("Shift+Tab" if backwards else "Tab")
        tag, focused_role, name = (focused(page).split("|", 2) + ["", "", ""])[:3]
        if tag != "main" and text.lower() in f"{tag}|{name}".lower() and role in (None, focused_role):
            return
    pytest.fail(f"could not reach {text!r} with the keyboard (last focus: {focused(page)[:80]!r})")


@pytest.fixture(scope="module")
def page(browser, app_url):
    page = open_app(browser, app_url)
    yield page
    page.close()


# The steps continue where the previous one left off.


def test_the_first_stops_are_the_skip_link_the_language_and_the_tabs(page):
    page.keyboard.press("Tab")
    assert "skip to main content" in focused(page).lower()
    tab_to(page, "Språk", limit=2)
    tab_to(page, "Logga in", limit=3, role="tab")


def test_registering_with_the_keyboard(page):
    page.keyboard.press("ArrowRight")  # the tab list: "Skapa konto"
    assert "Skapa konto" in focused(page)
    tab_to(page, "Användarnamn", limit=3)
    page.keyboard.type("Tangentbord")
    page.keyboard.press("Tab")
    page.keyboard.type(TEST_PASSWORD)
    tab_to(page, "Upprepa lösenordet", limit=3)
    page.keyboard.type(TEST_PASSWORD)
    page.keyboard.press("Enter")
    settle(page)
    assert page.get_by_text("Inloggad som").count() == 1


def test_adding_an_item_with_the_keyboard(page):
    tab_to(page, "Lägg till ett köp manuellt")
    page.keyboard.press("Enter")
    settle(page)
    tab_to(page, "Vara", limit=5)
    page.keyboard.type("Kaffe")
    page.keyboard.press("Tab")
    page.keyboard.type("59.9")
    tab_to(page, "Lägg till i listan", limit=5)
    page.keyboard.press("Enter")
    settle(page)
    assert page.get_by_text("Gå igenom varor utan kategori").count() == 1


def test_the_list_can_be_reached_with_the_keyboard(page):
    # st.data_editor draws on a canvas that takes focus; Streamlit adds a hidden
    # table (role grid) for screen readers.
    tab_to(page, "canvas|", limit=60)
    # The hidden table is added shortly after the canvas is drawn; wait for it.
    page.locator('[data-testid="stDataFrame"] table[role="grid"]').first.wait_for(state="attached", timeout=10_000)


def test_choosing_a_category_in_the_popup_with_the_keyboard(page):
    tab_to(page, "Gå igenom varor utan kategori", backwards=True)
    page.keyboard.press("Enter")
    settle(page)
    assert page.get_by_role("dialog").count() == 1
    tab_to(page, "Bröd", limit=15)
    page.keyboard.press("Enter")
    settle(page)
    assert page.get_by_role("dialog").count() == 0
    assert page.get_by_text("Alla varor har nu en kategori").count() == 1


def test_saving_and_switching_to_history_with_the_keyboard(page):
    tab_to(page, "💾 Spara")
    page.keyboard.press("Enter")
    settle(page)
    tab_to(page, "Aktuellt kvitto", backwards=True)
    page.keyboard.press("ArrowRight")  # the tab list: "Historik"
    settle(page)
    assert page.get_by_text("Utgifter per kategori").count() == 1


def test_opening_settings_with_the_keyboard(page):
    tab_to(page, "Inställningar", backwards=True, limit=80)
    page.keyboard.press("Enter")
    settle(page)
    tab_to(page, "Högsta belopp per vara", limit=5)
