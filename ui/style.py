"""The app's own CSS on top of the Streamlit theme: a linen background and sections as cards.

The colours come from the theme ([theme] in .streamlit/config.toml, THEME in
desktop/launcher.py); this file only adds what a theme cannot: a faint woven
pattern behind everything, and light "cards" for the sections (expanders,
forms, metrics, bordered containers) so tables and numbers keep good contrast.

Everything is inline: the pattern is an SVG in a data: URI, so nothing is
fetched from the network (the app works offline and tells no server when it
is opened) and the desktop build needs no extra files. The selectors are
Streamlit's data-testid attributes; if an update renames one, that part
simply falls back to the plain theme.
"""

from base64 import b64encode
from html import escape
from urllib.parse import quote

import streamlit as st

from core.i18n import LANGUAGES

CARD = "#FFFDF8"  # warm white, a step lighter than the background (#F4EFE6)
CARD_BORDER = "#DDD3C2"  # a soft edge for the cards (decorative; controls have the theme's darker one)
# Secondary text that Streamlit fades too much on its own (the upload box's "5MB per file"):
# at least 4.5:1 on the sand, the background and the cards (tests/test_accessibility.py).
MUTED_TEXT = "#56605A"

# A faint linen weave: thin warm lines a few pixels apart, in both directions. Text
# lies on it, so tests/test_accessibility.py checks the text against these colours too
# (axe-core cannot measure contrast over a background image).
LINEN_COLOURS = ("#E9E1D2", "#EEE7DA")
_LINEN_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='6' height='6'>"
    f"<path d='M0 1.5h6M0 4.5h6' stroke='{LINEN_COLOURS[0]}' stroke-width='0.6'/>"
    f"<path d='M1.5 0v6M4.5 0v6' stroke='{LINEN_COLOURS[1]}' stroke-width='0.6'/>"
    "</svg>"
)
LINEN_URI = "data:image/svg+xml," + quote(_LINEN_SVG)

# The logo: a warm-white receipt with a torn bottom edge and three lines, on a
# rounded square in the accent green. Used as the browser tab icon, in the
# sidebar (st.logo) and next to the title.
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="15" fill="#2F5D4E"/>'
    '<path d="M20 13H44V49L40 46L36 49L32 46L28 49L24 46L20 49Z" fill="#FFFDF8"/>'
    '<path d="M25.5 22.5H38.5M25.5 29H38.5M25.5 35.5H33" stroke="#2F5D4E" '
    'stroke-width="2.6" stroke-linecap="round"/>'
    "</svg>"
)
LOGO_URI = "data:image/svg+xml;base64," + b64encode(LOGO_SVG.encode("utf-8")).decode("ascii")

CSS = f"""
<style>
[data-testid="stApp"] {{
  background-image: url("{LINEN_URI}");
  background-repeat: repeat;
}}
[data-testid="stHeader"] {{
  background: transparent;
}}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {{
  color: {MUTED_TEXT};
}}
.eh-brand {{
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin: 0.25rem 0 0.75rem;
}}
.eh-brand img {{
  width: 3rem;
  height: 3rem;
}}
.eh-brand h1 {{
  margin: 0;
  padding: 0;
  font-family: "Source Serif", serif;
  font-size: 2.75rem;
  font-weight: 700;
  line-height: 1.1;
  color: #24332D;
}}
[data-testid="stExpander"] details,
[data-testid="stForm"],
[data-testid="stMetric"],
[data-testid="stVerticalBlockBorderWrapper"] {{
  background-color: {CARD};
  border: 1px solid {CARD_BORDER};
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(47, 93, 78, 0.06), 0 4px 14px rgba(47, 93, 78, 0.05);
}}
[data-testid="stMetric"] {{
  padding: 0.9rem 1.1rem;
}}
[data-testid="stExpander"] [data-testid="stForm"],
[data-testid="stSidebar"] [data-testid="stForm"],
[role="dialog"] [data-testid="stForm"] {{
  background-color: transparent;
  border: none;
  box-shadow: none;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{
  box-shadow: none;
}}
</style>
"""


def apply_style():
    """Add the CSS and the logo in the sidebar; call once per run, right after st.set_page_config."""
    st.html(CSS)
    st.logo(LOGO_SVG, size="large")


def page_language_script(lang):
    """A one-line script that sets <html lang>, so screen readers use the right voice.

    Streamlit always writes lang="en". `lang` is checked against LANGUAGES, so
    nothing else can end up in the script.
    """
    if lang not in LANGUAGES:
        raise ValueError(f"unknown language {lang!r}")
    return f'<script>document.documentElement.lang = "{lang}";</script>'


def render_title(title, lang):
    """The page title next to the logo, and the page language for screen readers.

    One element for both: Streamlit puts a gap after every element, so a
    separate one for the (invisible) script would push the page down. The
    title text is escaped; the script runs in the page, not in an iframe.
    """
    st.html(
        f'<div class="eh-brand"><img src="{LOGO_URI}" alt=""><h1>{escape(title)}</h1></div>'
        + page_language_script(lang),
        unsafe_allow_javascript=True,
    )
