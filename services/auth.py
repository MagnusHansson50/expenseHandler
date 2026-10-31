"""Login, registration and password reset flows (core.auth + database, no Streamlit).

Errors for the UI to handle:
- InvalidPassword(problem) when a new password breaks the rules
- db.UserNameError when a new user name is rejected
- LoginLocked(seconds_left) after too many failed logins for a name
- sqlite3.Error when the database fails
"""

import threading
import time

from core.auth import hash_password, password_problem, verify_password
from integrations import db

MAX_FAILED_LOGINS = 5  # failed attempts in a row before a name is locked
LOCK_SECONDS = 30  # how long a locked name has to wait


class InvalidPassword(ValueError):
    """A new password breaks the rules; `problem` is a core.receipt.Problem to translate."""

    def __init__(self, problem):
        super().__init__(problem.key)
        self.problem = problem


class LoginLocked(Exception):
    """Too many failed logins for this name; try again in `seconds_left` seconds."""

    def __init__(self, seconds_left):
        super().__init__(f"locked for {seconds_left} s")
        self.seconds_left = seconds_left


class LoginThrottle:
    """Counts failed logins per user name and locks a name after too many.

    Kept in server memory and shared by all browser tabs, so reloading the
    page does not reset it. It is reset when the server restarts. Names are
    compared case-insensitively, so "anna" and "Anna" count together.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()  # Streamlit serves sessions from several threads
        self._failures = {}  # key -> (failed attempts in a row, locked until)

    @staticmethod
    def _key(name):
        return name.strip().casefold()

    def seconds_left(self, name):
        """Seconds until `name` may try again; 0 if it is not locked."""
        with self._lock:
            _, locked_until = self._failures.get(self._key(name), (0, 0.0))
        return max(0, int(locked_until - self._clock() + 0.999))

    def record_failure(self, name):
        with self._lock:
            key = self._key(name)
            failures, _ = self._failures.get(key, (0, 0.0))
            failures += 1
            if failures >= MAX_FAILED_LOGINS:
                self._failures[key] = (0, self._clock() + LOCK_SECONDS)
            else:
                self._failures[key] = (failures, 0.0)

    def reset(self, name):
        with self._lock:
            self._failures.pop(self._key(name), None)


login_throttle = LoginThrottle()

# Checked against when the user name does not exist, so an unknown name takes
# as long as a wrong password and response times do not reveal which names exist.
_DUMMY_HASH, _DUMMY_SALT = hash_password("timing-equalizer-not-a-real-password")


def register(name, password, default_categories):
    """Create a user with a password and return the new db.User.

    Raises InvalidPassword or db.UserNameError (nothing is created then).
    """
    problem = password_problem(password)
    if problem:
        raise InvalidPassword(problem)
    password_hash, salt = hash_password(password)
    user_id = db.create_user_with_password(name, password_hash, salt, default_categories)
    return db.get_user(user_id)


def authenticate(name, password, throttle=login_throttle):
    """Return the db.User if name and password match, otherwise None.

    Raises LoginLocked while the name is locked after too many failures
    (the password is not checked then). A wrong password and an unknown
    name give the same result and take about the same time.
    """
    seconds_left = throttle.seconds_left(name)
    if seconds_left:
        raise LoginLocked(seconds_left)

    login = db.get_login(name)
    if login is None:
        verify_password(password, _DUMMY_HASH, _DUMMY_SALT)
        throttle.record_failure(name)
        return None
    if not verify_password(password, login.password_hash, login.salt):
        throttle.record_failure(name)
        return None

    throttle.reset(name)
    return login.user


def reset_password(name, new_password):
    """Set a new password for an existing user (used by scripts/reset_password.py).

    Returns False if there is no user with that name. Raises InvalidPassword
    if the new password breaks the rules.
    """
    problem = password_problem(new_password)
    if problem:
        raise InvalidPassword(problem)
    user = db.get_user_by_name(name)
    if user is None:
        return False
    password_hash, salt = hash_password(new_password)
    return db.set_password(user.id, password_hash, salt)
