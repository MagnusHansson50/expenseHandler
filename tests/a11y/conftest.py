"""The running app and a browser for the accessibility tests (tests/a11y).

Needs Playwright (requirements-a11y.txt and `python -m playwright install
chromium`); without it these tests are skipped, as in the normal test job.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="Playwright is not installed (requirements-a11y.txt)")

from desktop.launcher import free_port  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    """The app running like `streamlit run app.py` (config.toml applies) with a throwaway database."""
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


@pytest.fixture(scope="session")
def browser():
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()
