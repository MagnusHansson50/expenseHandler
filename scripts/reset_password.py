"""Set a new password for a user who has forgotten theirs.

The app cannot send reset e-mails, so whoever runs the app resets passwords
from the command line on the same computer:

    .venv/Scripts/python.exe scripts/reset_password.py "Anna"

The new password is typed twice without being shown (getpass) and is never
printed or logged. Uses expenses.db, or EXPENSES_DB_PATH if it is set.
This is an admin tool, so its messages are in English.
"""

import getpass
import sys
from pathlib import Path

# Allow running as a plain script from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.constants import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH  # noqa: E402
from integrations import db  # noqa: E402
from services import auth  # noqa: E402

EXIT_OK = 0
EXIT_UNKNOWN_USER = 1
EXIT_BAD_INPUT = 2


def main(argv, ask_password=getpass.getpass, out=print):
    """Run the reset; returns an exit code. `ask_password` and `out` are replaceable for tests."""
    if len(argv) != 1 or not argv[0].strip():
        out('Usage: python scripts/reset_password.py "<user name>"')
        return EXIT_BAD_INPUT
    name = argv[0]

    db.init_db()
    if db.get_user_by_name(name) is None:
        out(f"No user named '{name.strip()}' in {db.DB_PATH}.")
        return EXIT_UNKNOWN_USER

    password = ask_password(f"New password ({MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters): ")
    repeated = ask_password("Repeat the new password: ")
    if password != repeated:
        out("The passwords do not match. Nothing was changed.")
        return EXIT_BAD_INPUT

    try:
        auth.reset_password(name, password)
    except auth.InvalidPassword as error:
        out(f"The password was not accepted ({error.problem.key}). Nothing was changed.")
        return EXIT_BAD_INPUT

    out(f"The password for '{name.strip()}' has been changed.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
