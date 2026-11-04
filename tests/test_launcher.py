"""desktop/launcher.py: data folder, port, Streamlit flags and the reset-password passthrough."""

import socket
import tomllib
from pathlib import Path

import pytest

from desktop import launcher

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def restore_streamlit_config():
    """Starting the launcher loads its flags into Streamlit's global config; undo that afterwards."""
    from streamlit import config
    from streamlit.web import bootstrap

    script_path = config._main_script_path
    yield
    config._main_script_path = script_path
    bootstrap.load_config_options(flag_options={})


# --- Data folder -----------------------------------------------------------


def test_windows_data_folder_is_under_appdata(tmp_path):
    folder = launcher.data_dir("win32", {"APPDATA": str(tmp_path)}, home=tmp_path / "home")
    assert folder == tmp_path / "ExpenseHandler"


def test_windows_without_appdata_uses_the_roaming_folder(tmp_path):
    assert launcher.data_dir("win32", {}, home=tmp_path) == tmp_path / "AppData" / "Roaming" / "ExpenseHandler"


def test_mac_data_folder(tmp_path):
    expected = tmp_path / "Library" / "Application Support" / "ExpenseHandler"
    assert launcher.data_dir("darwin", {}, home=tmp_path) == expected


@pytest.mark.parametrize("env, expected", [({}, ".local/share"), ({"XDG_DATA_HOME": "xdg"}, "xdg")])
def test_linux_data_folder(tmp_path, env, expected):
    env = {key: str(tmp_path / value) for key, value in env.items()}
    assert launcher.data_dir("linux", env, home=tmp_path) == tmp_path / expected / "ExpenseHandler"


def test_use_data_dir_creates_the_folder_and_sets_the_database_path(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "data_dir", lambda env: tmp_path / "ExpenseHandler")
    env = {}
    path = launcher.use_data_dir(env)
    assert path == tmp_path / "ExpenseHandler" / "expenses.db"
    assert env["EXPENSES_DB_PATH"] == str(path)
    assert path.parent.is_dir()


def test_an_existing_database_path_wins(tmp_path):
    env = {"EXPENSES_DB_PATH": str(tmp_path / "manual.db")}
    assert launcher.use_data_dir(env) == tmp_path / "manual.db"
    assert env["EXPENSES_DB_PATH"] == str(tmp_path / "manual.db")


# --- Port and Streamlit settings -------------------------------------------


def test_free_port_can_be_listened_on_locally():
    port = launcher.free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def flags_as_config(flags):
    """{"server_address": ...} -> {"server": {"address": ...}}, like config.toml."""
    config = {}
    for name, value in flags.items():
        section, option = name.split("_", 1)
        config.setdefault(section, {})[option] = value
    return config


def test_security_settings_match_the_streamlit_config_file():
    config = tomllib.loads((REPO_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    flags = flags_as_config(launcher.streamlit_flags(8501))
    for section, options in config.items():
        for option, value in options.items():
            assert flags[section][option] == value, f"{section}.{option}"


def test_desktop_flags_listen_locally_on_the_given_port_without_dev_mode_or_telemetry():
    flags = launcher.streamlit_flags(8765)
    assert flags["server_address"] == "localhost"
    assert flags["server_port"] == 8765
    assert flags["global_developmentMode"] is False
    assert flags["browser_gatherUsageStats"] is False


def test_the_app_is_found_next_to_the_launcher_when_not_packaged():
    assert (launcher.bundle_dir() / "app.py").is_file()


# --- Starting ---------------------------------------------------------------


def test_reset_password_runs_the_script_with_the_data_folder_database(tmp_path, monkeypatch):
    from scripts import reset_password

    monkeypatch.setenv("EXPENSES_DB_PATH", str(tmp_path / "expenses.db"))
    calls = []
    monkeypatch.setattr(reset_password, "main", lambda argv: calls.append(argv) or 0)
    assert launcher.main(["--reset-password", "Anna"]) == 0
    assert calls == [["Anna"]]


def test_starting_prints_where_it_runs_and_starts_streamlit_with_the_flags(tmp_path, monkeypatch, capsys):
    from streamlit.web import bootstrap

    monkeypatch.setenv("EXPENSES_DB_PATH", str(tmp_path / "expenses.db"))
    monkeypatch.setattr(launcher, "free_port", lambda: 8765)
    monkeypatch.setattr(launcher, "open_browser_when_ready", lambda url: None)
    runs = []
    monkeypatch.setattr(bootstrap, "run", lambda *args: runs.append(args))

    assert launcher.main([]) == 0
    script, is_hello, args, flags = runs[0]
    assert Path(script) == launcher.bundle_dir() / "app.py"
    assert flags == launcher.streamlit_flags(8765)
    output = capsys.readouterr().out
    assert "http://localhost:8765" in output
    assert str(tmp_path / "expenses.db") in output


def test_the_flags_are_in_effect_when_the_server_starts(tmp_path, monkeypatch):
    """bootstrap.run does not apply flags by itself; the launcher must load them first."""
    from streamlit import config
    from streamlit.web import bootstrap

    monkeypatch.setenv("EXPENSES_DB_PATH", str(tmp_path / "expenses.db"))
    seen = {}

    def fake_run(script, is_hello, args, flags):
        for option in ("server.port", "server.address", "server.maxUploadSize", "global.developmentMode",
                       "client.showErrorDetails", "browser.gatherUsageStats"):
            seen[option] = config.get_option(option)

    monkeypatch.setattr(bootstrap, "run", fake_run)
    launcher.main(["--port", "8765", "--no-browser"])
    assert seen == {
        "server.port": 8765,
        "server.address": "localhost",
        "server.maxUploadSize": 5,
        "global.developmentMode": False,
        "client.showErrorDetails": "none",
        "browser.gatherUsageStats": False,
    }


def test_browser_is_not_opened_if_the_app_never_answers(monkeypatch):
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    port = launcher.free_port()  # nothing listens here
    assert launcher.open_browser_when_ready(f"http://localhost:{port}", wait_seconds=1) is False
    assert opened == []


def test_port_can_be_chosen_and_the_browser_skipped(tmp_path, monkeypatch):
    from streamlit.web import bootstrap

    monkeypatch.setenv("EXPENSES_DB_PATH", str(tmp_path / "expenses.db"))
    monkeypatch.setattr(launcher, "open_browser_when_ready", lambda url: pytest.fail("browser opened"))
    runs = []
    monkeypatch.setattr(bootstrap, "run", lambda *args: runs.append(args))
    assert launcher.main(["--port", "8601", "--no-browser"]) == 0
    assert runs[0][3]["server_port"] == 8601
