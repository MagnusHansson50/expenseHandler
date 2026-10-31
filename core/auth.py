"""Password hashing and password rules.

Pure Python (standard library only): no Streamlit and no database. Passwords
are never stored or logged; only a salted scrypt hash is kept.
"""

import hashlib
import hmac
import os
import unicodedata

from core.constants import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from core.receipt import Problem

# scrypt cost parameters: n=2**14, r=8, p=1 uses about 16 MB of memory and
# tens of milliseconds per hash - cheap for one login, expensive for guessing.
_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}
_HASH_BYTES = 64
_SALT_BYTES = 16


def _normalize(password):
    # NFKC so the same password typed on different keyboards/OSes hashes the same.
    return unicodedata.normalize("NFKC", password).encode("utf-8")


def _scrypt(password, salt):
    return hashlib.scrypt(_normalize(password), salt=salt, dklen=_HASH_BYTES, **_SCRYPT_PARAMS)


def password_problem(password):
    """Return a Problem if the password breaks the length rules, otherwise None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return Problem("password_too_short", {"min": MIN_PASSWORD_LENGTH})
    if len(password) > MAX_PASSWORD_LENGTH:
        return Problem("password_too_long", {"max": MAX_PASSWORD_LENGTH})
    return None


def hash_password(password):
    """Return (password_hash, salt) for storing; a new random salt every time."""
    salt = os.urandom(_SALT_BYTES)
    return _scrypt(password, salt), salt


def verify_password(password, password_hash, salt):
    """Return True if `password` matches the stored hash.

    Uses a constant-time comparison so the time taken does not reveal how much
    of the hash matched. Passwords longer than the limit are rejected without
    hashing them.
    """
    if len(password) > MAX_PASSWORD_LENGTH:
        return False
    return hmac.compare_digest(_scrypt(password, salt), password_hash)
