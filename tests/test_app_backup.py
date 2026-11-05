"""The backup section in the History tab. Its file contents are tested in test_services_backup.py;
uploading a backup is not supported by AppTest and is checked in a browser."""

from test_app import add_manual_purchase, create_user, start_app


def download_buttons(at):
    return {button.proto.label: button.proto.url for button in at.get("download_button")}


def test_backup_downloads_are_offered_once_logged_in(temp_db):
    at = start_app()
    create_user(at, "Anna")
    assert not at.exception
    assert "💾 Backup" in [expander.label for expander in at.expander]
    buttons = download_buttons(at)
    assert buttons["⬇️ Download backup"].endswith(".json")
    assert buttons["⬇️ Download history as CSV (Excel)"].endswith(".csv")


def test_backup_section_is_there_also_with_history(temp_db):
    at = start_app()
    create_user(at, "Anna")
    add_manual_purchase(at, "Coffee", 45.0)
    next(b for b in at.button if "Save" in b.label).click().run()
    assert not at.exception
    assert len(download_buttons(at)) == 2


def test_nothing_to_download_before_login(temp_db):
    at = start_app()
    assert download_buttons(at) == {}


def test_backup_texts_in_swedish(temp_db):
    at = start_app(lang="sv")
    create_user(at, "Anna")
    assert "💾 Säkerhetskopia" in [expander.label for expander in at.expander]
    assert "⬇️ Ladda ner säkerhetskopia" in download_buttons(at)
