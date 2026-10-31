"""Guard against personal data in tracked files (the repository is public).

The patterns are deliberately generic so this file itself contains no
personal data: local user folders, business OneDrive folders (they include
the organisation name) and e-mail addresses that are not known to be safe.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATTERNS = {
    "local user folder": re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
    # Written with \s so this line does not match itself.
    "business OneDrive folder": re.compile(r"OneDrive\s-\s", re.IGNORECASE),
}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ALLOWED_EMAIL_DOMAINS = ("users.noreply.github.com", "anthropic.com", "example.com")


def tracked_text_files():
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    for name in result.stdout.splitlines():
        path = REPO_ROOT / name
        try:
            yield name, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binary or deleted in the working tree


def test_no_personal_paths_in_tracked_files():
    findings = [
        f"{name}:{line_no}: {label}"
        for name, text in tracked_text_files()
        for line_no, line in enumerate(text.splitlines(), 1)
        for label, pattern in FORBIDDEN_PATTERNS.items()
        if pattern.search(line)
    ]
    assert not findings, "Personal paths found:\n" + "\n".join(findings)


def test_no_personal_email_addresses_in_tracked_files():
    findings = [
        f"{name}:{line_no}"
        for name, text in tracked_text_files()
        for line_no, line in enumerate(text.splitlines(), 1)
        for address in EMAIL.findall(line)
        if not address.lower().endswith(ALLOWED_EMAIL_DOMAINS)
    ]
    assert not findings, "E-mail addresses found:\n" + "\n".join(findings)
