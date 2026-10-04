from __future__ import annotations

from colt_integrations.fetch.normalize import html_to_text


def test_extracts_title_and_strips_markup() -> None:
    html = """
    <html><head><title>Acme Corp</title><style>.x{color:red}</style></head>
    <body><h1>Welcome</h1><p>Acme makes <b>rockets</b>.</p></body></html>
    """

    title, text = html_to_text(html)

    assert title == "Acme Corp"
    assert "Welcome" in text
    assert "Acme makes" in text
    assert "rockets" in text
    assert "color:red" not in text
    assert "<" not in text


def test_strips_script_tags_entirely() -> None:
    html = "<html><body><script>alert('hi')</script><p>Real content</p></body></html>"

    _, text = html_to_text(html)

    assert "alert" not in text
    assert "Real content" in text


def test_collapses_repeated_whitespace_within_a_line() -> None:
    _, text = html_to_text("<p>line   one</p>")

    assert text == "line one"


def test_never_produces_more_than_one_blank_line_in_a_row() -> None:
    html = "<div><div><div>padded</div></div></div><p>next</p>"

    _, text = html_to_text(html)

    assert "\n\n\n" not in text


def test_no_title_tag_returns_none() -> None:
    title, text = html_to_text("<body><p>no title here</p></body>")

    assert title is None
    assert "no title here" in text
