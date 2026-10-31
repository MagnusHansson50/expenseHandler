"""Helpers for showing user-provided text safely."""

import re
import string

# Every ASCII punctuation character may be backslash-escaped in Markdown
# (CommonMark). Escaping all of them neutralises Markdown syntax, Streamlit's
# :color[...] / :emoji: syntax and $LaTeX$.
_MARKDOWN_SPECIAL = re.compile("([" + re.escape(string.punctuation) + "])")

# GitHub-flavoured Markdown turns bare URLs and e-mail addresses into links
# after escapes are resolved, so escaping alone is not enough. An invisible
# WORD JOINER breaks the patterns it looks for: "scheme://", "www." and "x@y".
_WORD_JOINER = "\u2060"
_AUTOLINK_TRIGGERS = re.compile(r"(:)(?=//)|(?<=www)(?=\.)|(@)", re.IGNORECASE)


def escape_markdown(text):
    """Return `text` so Streamlit shows it literally instead of as Markdown.

    Use it for every piece of user-provided text (user names, category names,
    item names) that is passed to a Markdown-rendering element such as
    st.caption, st.success or st.error. Line breaks are flattened to spaces,
    and an invisible word joiner is inserted where Markdown would otherwise
    create a link from a bare URL or e-mail address.
    """
    single_line = " ".join(str(text).split())
    unlinkable = _AUTOLINK_TRIGGERS.sub(lambda m: (m.group(0) or "") + _WORD_JOINER, single_line)
    return _MARKDOWN_SPECIAL.sub(r"\\\1", unlinkable)
