"""Start ExpenseHandler as a desktop program.

This is the entry point of the packaged program (PyInstaller), and it also
runs from the repository:

    .venv/Scripts/python.exe desktop/launcher.py
    .venv/Scripts/python.exe desktop/launcher.py --reset-password "Anna"
    .venv/Scripts/python.exe desktop/launcher.py --port 8600 --no-browser

It keeps the database in the user's own data folder (so it survives updates
of the program), starts Streamlit on a free port on this computer only, and
opens the browser when the app is ready. All security settings are passed as
flags, because .streamlit/config.toml is not read inside a packaged program.
EXPENSES_DB_PATH, if already set, still wins (used for manual testing).
"""

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# Allow running as a plain script from the repository root.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.i18n import LANGUAGES, t  # noqa: E402

APP_NAME = "ExpenseHandler"
DB_FILE_NAME = "expenses.db"
HOST = "localhost"
BROWSER_WAIT_SECONDS = 60  # give up opening the browser after this; the URL is printed anyway


def data_dir(platform=sys.platform, env=os.environ, home=None):
    """The folder for the user's data on this operating system."""
    home = Path(home) if home else Path.home()
    if platform == "win32":
        base = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    return base / APP_NAME


def bundle_dir():
    """Where app.py is: inside the PyInstaller bundle, or the repository root."""
    return Path(getattr(sys, "_MEIPASS", REPO_ROOT))


def free_port():
    """A TCP port on this computer that nothing listens on right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def streamlit_flags(port):
    """Streamlit config options for the desktop program, as bootstrap.run expects them.

    The security settings match .streamlit/config.toml (tests/test_launcher.py
    checks this). developmentMode must be off explicitly: Streamlit guesses it
    from not being installed in site-packages, which is true in a bundle, and
    would then try to load its UI from a development server.
    """
    return {
        "server_address": HOST,
        "server_port": port,
        "server_headless": True,  # we open the browser ourselves, once the app answers
        "server_maxUploadSize": 5,
        "server_fileWatcherType": "none",
        "client_showErrorDetails": "none",
        "browser_gatherUsageStats": False,
        "global_developmentMode": False,
    }


def use_data_dir(env=os.environ):
    """Point the app at the database in the user's data folder, unless EXPENSES_DB_PATH is set.

    Returns the database path in use.
    """
    configured = env.get("EXPENSES_DB_PATH", "").strip()  # blank counts as not set, as in db.database_path
    if configured:
        env["EXPENSES_DB_PATH"] = configured
        return Path(configured)
    folder = data_dir(env=env)
    folder.mkdir(parents=True, exist_ok=True)
    env["EXPENSES_DB_PATH"] = str(folder / DB_FILE_NAME)
    return Path(env["EXPENSES_DB_PATH"])


def open_browser_when_ready(url, wait_seconds=BROWSER_WAIT_SECONDS):
    """Poll Streamlit's health endpoint, then open the app in the default browser."""
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2):
                webbrowser.open(url)
                return True
        except OSError:
            time.sleep(0.5)  # not up yet
    return False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    db_path = use_data_dir()

    if argv[:1] == ["--reset-password"]:
        from scripts import reset_password  # after use_data_dir: it reads EXPENSES_DB_PATH

        return reset_password.main(argv[1:])

    # --port N picks the port (for testing the build); --no-browser skips opening it.
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else free_port()
    url = f"http://{HOST}:{port}"
    for lang in LANGUAGES:
        print(t("desktop_running", lang, url=url, path=str(db_path)))
    if "--no-browser" not in argv:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()

    start_streamlit(str(bundle_dir() / "app.py"), streamlit_flags(port))
    return 0


def start_streamlit(script, flags):
    """Run the app like `streamlit run` does; blocks until the server stops.

    bootstrap.run does not apply the flags itself: `streamlit run` first
    records the script path and loads the config options, so we do the same.
    """
    from streamlit import config as streamlit_config
    from streamlit.web import bootstrap

    streamlit_config._main_script_path = script  # where Streamlit looks for config and secrets
    bootstrap.load_config_options(flag_options=flags)
    bootstrap.run(script, False, [], flags)


if __name__ == "__main__":
    sys.exit(main())
