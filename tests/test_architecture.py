"""Module dependencies follow the layers described in CLAUDE.md.

app.py -> ui/, services/, core/, integrations/
ui/ -> ui/, services/, core/, integrations/ (never app.py)
services/ -> core/, integrations/ (no Streamlit)
core/ -> core/ only (no Streamlit, no database)
integrations/ -> core/constants.py only
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def modules_in(package):
    return sorted((REPO_ROOT / package).rglob("*.py"))  # subpackages too (core/receipt_formats)


@pytest.mark.parametrize("path", modules_in("core"), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_core_has_no_streamlit_database_or_higher_layers(path):
    forbidden = ("streamlit", "sqlite3", "integrations", "services")
    bad = [m for m in imported_modules(path) if m.split(".")[0] in forbidden]
    assert not bad, f"{path.name} imports {bad}"


@pytest.mark.parametrize("path", modules_in("services"), ids=lambda p: p.name)
def test_services_have_no_streamlit(path):
    bad = [m for m in imported_modules(path) if m.split(".")[0] == "streamlit"]
    assert not bad, f"{path.name} imports {bad}"


@pytest.mark.parametrize("path", modules_in("ui"), ids=lambda p: p.name)
def test_ui_does_not_import_app(path):
    bad = [m for m in imported_modules(path) if m.split(".")[0] == "app"]
    assert not bad, f"{path.name} imports {bad}"


@pytest.mark.parametrize(
    "path",
    [*modules_in("core"), *modules_in("services"), *modules_in("integrations")],
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_nothing_below_the_ui_imports_it(path):
    bad = [m for m in imported_modules(path) if m.split(".")[0] in ("ui", "app")]
    assert not bad, f"{path.name} imports {bad}"


@pytest.mark.parametrize("path", modules_in("integrations"), ids=lambda p: p.name)
def test_integrations_only_use_core_constants(path):
    project = [m for m in imported_modules(path) if m.split(".")[0] in ("core", "services", "streamlit")]
    assert set(project) <= {"core.constants"}, f"{path.name} imports {project}"
