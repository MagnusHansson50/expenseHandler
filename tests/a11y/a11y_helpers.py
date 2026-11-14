"""Helpers shared by the accessibility tests (a module of its own: tests/conftest.py exists too)."""

TEST_PASSWORD = "test-password-1"  # made up, for a throwaway database only


def open_app(browser, app_url):
    """A new page (its own Streamlit session) on the Swedish login page."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(f"{app_url}/?lang=sv")
    page.get_by_text("Logga in för att se dina kvitton").wait_for()
    settle(page)
    return page


def settle(page):
    """Wait until Streamlit has finished the run the last action started."""
    page.wait_for_timeout(300)
    page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden", timeout=15_000)
    page.wait_for_timeout(300)
