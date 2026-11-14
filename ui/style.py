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

from urllib.parse import quote

import streamlit as st

CARD = "#FFFDF8"  # warm white, a step lighter than the background (#F4EFE6)
CARD_BORDER = "#DDD3C2"  # the theme's borderColor

# A faint linen weave: thin warm lines a few pixels apart, in both directions.
_LINEN_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='6' height='6'>"
    "<path d='M0 1.5h6M0 4.5h6' stroke='#E9E1D2' stroke-width='0.6'/>"
    "<path d='M1.5 0v6M4.5 0v6' stroke='#EEE7DA' stroke-width='0.6'/>"
    "</svg>"
)
LINEN_URI = "data:image/svg+xml," + quote(_LINEN_SVG)

CSS = f"""
<style>
[data-testid="stApp"] {{
  background-image: url("{LINEN_URI}");
  background-repeat: repeat;
}}
[data-testid="stHeader"] {{
  background: transparent;
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
    """Add the CSS to the page; call once per run, right after st.set_page_config."""
    st.html(CSS)
