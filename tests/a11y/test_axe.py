"""Automated accessibility audit with axe-core: every view of the real app in Chromium.

Runs only where Playwright and axe-playwright-python are installed
(requirements-a11y.txt and `python -m playwright install chromium`); the
normal test run skips it. The CI job `a11y` runs it:

    python -m pytest tests/a11y

The app is started like `streamlit run app.py` (so .streamlit/config.toml
applies) with a throwaway database, a test user is registered with a made-up
password, and axe checks each view against WCAG 2.1 A and AA. A view fails on
any violation that is not in KNOWN_STREAMLIT_ISSUES. axe-core finds about a
third of all accessibility problems; keyboard use and screen readers are
checked by hand (see README).
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="Playwright is not installed (requirements-a11y.txt)")
axe_module = pytest.importorskip(
    "axe_playwright_python.sync_playwright", reason="axe-playwright-python is not installed"
)

from desktop.launcher import free_port  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
TEST_PASSWORD = "test-password-1"  # made up, for a throwaway database only

# Violations inside Streamlit's own widgets that the app cannot change. Each
# entry: axe rule id -> why it is accepted. Keep this list short and explained.
KNOWN_STREAMLIT_ISSUES = {}


@pytest.fixture(scope="module")
def app_url(tmp_path_factory):
    """The app running on localhost with a throwaway database; stopped afterwards."""
    port = free_port()
    database = tmp_path_factory.mktemp("a11y") / "a11y.db"
    env = {**os.environ, "EXPENSES_DB_PATH": str(database)}
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port),
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://localhost:{port}"
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("the app did not start")
        yield url
    finally:
        server.terminate()
        server.wait(timeout=30)


@pytest.fixture(scope="module")
def page(app_url):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{app_url}/?lang=sv")
        page.get_by_text("Logga in för att se dina kvitton").wait_for()
        yield page
        browser.close()


def violations(page):
    """axe-core's WCAG 2.1 A/AA violations on the page, minus the known Streamlit ones."""
    results = axe_module.Axe().run(page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
    return [
        violation for violation in results.response["violations"]
        if violation["id"] not in KNOWN_STREAMLIT_ISSUES
    ]


def describe(found):
    lines = []
    for violation in found:
        targets = [", ".join(node["target"]) for node in violation["nodes"][:3]]
        lines.append(f"{violation['id']} ({violation['impact']}): {violation['help']} -> {targets}")
    return "\n".join(lines)


def settle(page):
    """Wait until Streamlit has finished the run the last action started."""
    page.wait_for_timeout(300)
    page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden", timeout=15_000)
    page.wait_for_timeout(300)


# The views are visited in order: each test continues where the previous one left off.


def test_login_page(page):
    found = violations(page)
    assert not found, describe(found)


def test_receipt_tab_after_registering(page):
    page.get_by_role("tab", name="Skapa konto").click()
    page.locator(".st-key-register_name input").fill("Tillganglig")
    page.locator(".st-key-register_password input").fill(TEST_PASSWORD)
    page.locator(".st-key-register_password_repeat input").fill(TEST_PASSWORD)
    page.locator(".st-key-register_submit button").click()
    page.get_by_text("Inloggad som").wait_for()
    settle(page)
    found = violations(page)
    assert not found, describe(found)


def test_receipt_tab_with_an_item(page):
    page.locator('[data-testid="stExpander"] summary', has_text="Lägg till ett köp manuellt").click()
    page.get_by_label("Vara", exact=True).fill("Kaffe")
    page.get_by_label("Pris (kr)").fill("59.90")
    page.get_by_role("button", name="Lägg till i listan").click()
    page.locator(".st-key-review_open").wait_for()
    settle(page)
    found = violations(page)
    assert not found, describe(found)


def test_review_popup(page):
    page.locator(".st-key-review_open button").click()
    page.get_by_role("dialog").wait_for()
    settle(page)
    found = violations(page)
    page.locator(".st-key-review_stop button").click()
    page.get_by_role("dialog").wait_for(state="hidden")
    settle(page)
    assert not found, describe(found)


def test_history_tab(page):
    page.locator('[data-testid="stMain"] button', has_text="💾 Spara").first.click()
    settle(page)
    page.get_by_role("tab", name="Historik").click()
    page.get_by_text("Utgifter per kategori").wait_for()
    settle(page)
    found = violations(page)
    assert not found, describe(found)


def test_settings_in_the_sidebar(page):
    page.locator('[data-testid="stSidebar"] [data-testid="stExpander"] summary', has_text="Inställningar").click()
    page.get_by_label("Högsta belopp per vara (kr)").wait_for()
    settle(page)
    found = violations(page)
    assert not found, describe(found)
