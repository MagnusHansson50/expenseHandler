# PyInstaller build of the desktop program. From the repository root:
#
#     .venv/Scripts/python.exe -m pip install -r requirements-build.txt
#     .venv/Scripts/python.exe -m PyInstaller desktop/ExpenseHandler.spec --noconfirm
#
# The result is the folder dist/ExpenseHandler (ExpenseHandler.exe plus its
# files): one folder, not one file, so it starts without unpacking itself to a
# temporary folder each time, which is also what antivirus programs object to.
#
# Streamlit runs app.py as a script, so PyInstaller cannot see what it imports:
# app.py is copied as a file and our packages are listed as hidden imports.
# Streamlit has no PyInstaller hook, so its web UI files, its package metadata
# (it reads its own version) and its lazily imported modules are collected here.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

REPO_ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is set by PyInstaller

hiddenimports = [
    *collect_submodules("core"),
    *collect_submodules("services"),
    *collect_submodules("integrations"),
    *collect_submodules("scripts"),
    *collect_submodules("streamlit"),
]

datas = [
    (str(REPO_ROOT / "app.py"), "."),
    *collect_data_files("streamlit"),
    *copy_metadata("streamlit"),
]

a = Analysis(  # noqa: F821
    [str(REPO_ROOT / "desktop" / "launcher.py")],
    pathex=[str(REPO_ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "PyPDF2"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ExpenseHandler",
    console=True,  # the window shows where the app runs; closing it quits the program
    upx=False,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="ExpenseHandler",
    upx=False,
)
