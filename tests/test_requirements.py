"""Dependencies must be pinned to tested versions, and PyPDF2 must not return."""

import re
from importlib.metadata import version
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PINNED = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)~=(?P<version>\d+\.\d+\.\d+)$")


def requirement_lines(filename):
    for line in (REPO_ROOT / filename).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-r ")):
            yield line


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements-dev.txt"])
def test_every_dependency_is_pinned_to_patch_releases(filename):
    unpinned = [line for line in requirement_lines(filename) if not PINNED.match(line)]
    assert not unpinned, f"{filename}: use 'name~=X.Y.Z' for {unpinned}"


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements-dev.txt"])
def test_installed_versions_satisfy_the_pins(filename):
    for line in requirement_lines(filename):
        match = PINNED.match(line)
        pinned = tuple(int(part) for part in match["version"].split("."))
        installed = tuple(int(part) for part in version(match["name"]).split(".")[:3])
        assert installed[:2] == pinned[:2] and installed >= pinned, (match["name"], installed)


def test_pypdf2_is_not_a_dependency():
    names = [PINNED.match(line)["name"].lower() for line in requirement_lines("requirements.txt")]
    assert "pypdf2" not in names
    assert "pypdf" in names
