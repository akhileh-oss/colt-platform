"""Document normalization (CLAUDE.md §68's Milestone 10 Build list): raw HTML to the plain text
a `ResearchAgent` reads and a `record_evidence` call quotes as an excerpt.

A minimal `html.parser.HTMLParser` subclass rather than a new dependency — this milestone needs
"strip markup, collapse whitespace, keep the title," not a readability algorithm that guesses
which part of a page is the "main content."
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP_TAGS = frozenset({"script", "style", "head", "noscript", "template"})
_BLOCK_TAGS = frozenset(
    {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}
)
_WHITESPACE_RUN = re.compile(r"[ \t\f\v]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self._in_title = False
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and self.title is None:
            # <title> lives inside <head>, which is itself a skipped tag — captured before the
            # skip check below, which exists to keep <head>/<script>/<style> text out of the
            # visible body, not to hide the title.
            stripped = data.strip()
            if stripped:
                self.title = stripped
        if self._skip_depth:
            return
        self._chunks.append(data)

    @property
    def text(self) -> str:
        joined = "".join(self._chunks)
        joined = _WHITESPACE_RUN.sub(" ", joined)
        lines = [line.strip() for line in joined.split("\n")]
        collapsed = "\n".join(line for line in lines if line)
        return _BLANK_LINE_RUN.sub("\n\n", collapsed).strip()


def html_to_text(html: str) -> tuple[str | None, str]:
    """Return `(title, text)` — `title` from `<title>` if present, `text` the page's visible
    content with markup, scripts and styles stripped and whitespace collapsed."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.title, parser.text
