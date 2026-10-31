import string

import pytest

from core.text import escape_markdown

WJ = "\u2060"  # invisible WORD JOINER inserted to stop automatic links


@pytest.mark.parametrize("text", ["Anna", "Bröd Levain 3", "Mjölk åäö ÅÄÖ", ""])
def test_plain_text_is_unchanged(text):
    assert escape_markdown(text) == text


def test_every_ascii_punctuation_character_is_escaped():
    escaped = escape_markdown(string.punctuation)
    assert escaped == "".join("\\" + char for char in string.punctuation).replace("@", "@" + WJ)


def test_markdown_image_and_link_are_neutralised():
    escaped = escape_markdown("Eve ![x](http://evil.test/p.png) [Click](https://evil.test)")
    assert escaped == (
        rf"Eve \!\[x\]\(http\:{WJ}\/\/evil\.test\/p\.png\) "
        rf"\[Click\]\(https\:{WJ}\/\/evil\.test\)"
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        ("http://evil.test", rf"http\:{WJ}\/\/evil\.test"),
        ("HTTPS://evil.test", rf"HTTPS\:{WJ}\/\/evil\.test"),
        ("www.evil.test", rf"www{WJ}\.evil\.test"),
        ("WWW.evil.test", rf"WWW{WJ}\.evil\.test"),
        ("me@example.com", rf"me\@{WJ}example\.com"),
    ],
)
def test_bare_urls_and_emails_cannot_become_links(text, expected):
    assert escape_markdown(text) == expected


def test_words_that_only_look_similar_are_untouched():
    assert escape_markdown("Ratio 3:1 and wwwx") == r"Ratio 3\:1 and wwwx"


def test_streamlit_specific_syntax_is_neutralised():
    assert escape_markdown(":red[Alert] :smile: $x^2$") == r"\:red\[Alert\] \:smile\: \$x\^2\$"


def test_line_breaks_and_extra_spaces_are_flattened():
    assert escape_markdown("  # Title\n\n- item  ") == r"\# Title \- item"


def test_non_string_values_are_converted():
    assert escape_markdown(ValueError("A user named 'x_y' already exists.")) == (
        r"A user named \'x\_y\' already exists\."
    )
