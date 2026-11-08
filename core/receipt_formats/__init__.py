"""Receipt layouts that can be imported, one module per layout.

Each module reads the text that pypdf extracted from one kind of receipt PDF
and offers the same three functions:

    matches(text) -> bool            is this text in my layout?
    parse_items(text) -> DataFrame   the items, with the columns Item and Price
    parse_paid_total(text) -> float | None   the amount paid, to check the items against

core.parser reads the PDF, picks the first layout in its FORMATS whose
matches() is true and calls the other two. To add a layout, add a module here
with these functions and list it in core.parser.FORMATS.
"""
