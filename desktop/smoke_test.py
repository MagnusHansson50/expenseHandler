"""Check that a built desktop program starts and answers. Used by the release workflow.

    python desktop/smoke_test.py dist/ExpenseHandler/ExpenseHandler.exe

Starts the program on a free port with a throwaway database, waits for
Streamlit's health endpoint and the page, then stops it. Exit code 0 if it
answered, 1 if not. The program's own output is printed for the build log.
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from desktop.launcher import free_port  # noqa: E402

START_TIMEOUT_SECONDS = 120


def answers(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status == 200
    except OSError:
        return False


def main(argv):
    if len(argv) != 1:
        print("Usage: python desktop/smoke_test.py <path to ExpenseHandler executable>")
        return 2
    port = free_port()
    url = f"http://localhost:{port}"
    with tempfile.TemporaryDirectory() as folder:
        env = {**os.environ, "EXPENSES_DB_PATH": str(Path(folder) / "smoke.db")}
        program = subprocess.Popen(
            # Absolute path: Windows does not find "dist/ExpenseHandler/..." as given.
            [str(Path(argv[0]).resolve()), "--port", str(port), "--no-browser"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            deadline = time.monotonic() + START_TIMEOUT_SECONDS
            while time.monotonic() < deadline and program.poll() is None:
                if answers(f"{url}/_stcore/health") and answers(url):
                    print(f"OK: the program answered at {url}")
                    return 0
                time.sleep(1)
            print(f"FAILED: no answer at {url} (exit code {program.poll()})")
            return 1
        finally:
            program.terminate()
            try:
                output, _ = program.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                program.kill()
                output, _ = program.communicate()
            print(output)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
