"""Small, deterministic HTML-to-visible-text helpers for untrusted pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


class _TextExtractor(HTMLParser):
    """Keep visible text and discard active elements with their contents."""

    _SUPPRESSED = frozenset({"script", "style", "template", "noscript"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._suppression_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in self._SUPPRESSED:
            self._suppression_depth += 1
        elif lowered == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self._SUPPRESSED and self._suppression_depth:
            self._suppression_depth -= 1
        elif lowered == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._suppression_depth == 0:
            self.parts.append(data)
            if self._in_title:
                self.title_parts.append(data)


def visible_text(value: Any, limit: int) -> str:
    """Extract compact visible text from untrusted HTML, capped by characters."""
    parser = _TextExtractor()
    parser.feed("" if value is None else str(value))
    parser.close()
    compact = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return compact[:limit]


def extract_page(value: Any, limit: int) -> tuple[str, str]:
    """Return a page title and compact visible body from one HTML document."""
    parser = _TextExtractor()
    parser.feed("" if value is None else str(value))
    parser.close()
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()[:240]
    body = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:limit]
    return title, body


__all__ = ["_TextExtractor", "extract_page", "visible_text"]
