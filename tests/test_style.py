"""ui/style.py: the app's own CSS stays offline and is put on every page."""

import re
import xml.etree.ElementTree as ElementTree
from urllib.parse import unquote

from ui import style

from test_app import create_user, start_app


def test_the_css_loads_nothing_from_the_network():
    # Only data: URIs: the app must work offline and tell no server when it is opened.
    urls = re.findall(r"url\(\s*['\"]?([^'\")]+)", style.CSS)
    assert urls, "expected the background pattern"
    assert all(url.startswith("data:") for url in urls), urls
    assert "@import" not in style.CSS


def test_the_background_pattern_is_valid_svg():
    svg = unquote(style.LINEN_URI.removeprefix("data:image/svg+xml,"))
    root = ElementTree.fromstring(svg)
    assert root.tag.endswith("svg")


def test_the_logo_is_valid_svg_and_inline():
    root = ElementTree.fromstring(style.LOGO_SVG)
    assert root.tag.endswith("svg")
    assert style.LOGO_URI.startswith("data:image/svg+xml;base64,")


def test_the_title_shows_the_logo_and_the_name(temp_db):
    at = start_app()
    bodies = [element.proto.body for element in at.get("html")]
    assert any('class="eh-brand"' in body and "<h1>ExpenseHandler</h1>" in body for body in bodies)


def test_the_style_is_on_the_login_page_and_after_logging_in(temp_db):
    at = start_app()
    assert any("stApp" in element.proto.body for element in at.get("html"))
    create_user(at, "Anna")
    assert any("stApp" in element.proto.body for element in at.get("html"))
