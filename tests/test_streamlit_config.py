"""The security settings in .streamlit/config.toml must stay in place."""

import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"


def load_config():
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def test_server_only_listens_on_localhost():
    assert load_config()["server"]["address"] == "localhost"


def test_upload_size_is_limited():
    assert 0 < load_config()["server"]["maxUploadSize"] <= 5


def test_error_details_are_hidden():
    assert load_config()["client"]["showErrorDetails"] == "none"
