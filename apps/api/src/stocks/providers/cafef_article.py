"""Full article text for one CafeF story, read off the published page.

The feed cannot supply this. CafeF's RSS `<item>` carries only
`title`/`link`/`description`/`pubDate`/`guid` — no `<content:encoded>` — and the
same is true of every Vietnamese finance feed measured beside it (VnExpress,
Vietstock, Thanh Nien, Vietnambiz, VnEconomy: 0 of 5 carry a full-text element).
Withholding the body is the publishers' policy, not a gap in the RSS parser, so
reading the article means fetching the article.

Extraction is a targeted read rather than a boilerplate-removal library. CafeF
wraps every story in `div.detail-content`, and inside it the prose sits as
*direct* children — `<p>`, `<h2>`/`<h3>`, `<figure>`, `<ul>` — while the widgets
that share the container (`div.tindnd` "TIN MỚI", `div.chisochungkhoan`, the
`h-show-pc`/`h-show-mobile` ad slots) are nested `<div>`s. Emitting only the
allowlisted blocks at depth 1 therefore drops the furniture without a denylist
that has to be maintained against whatever CafeF adds next. It also avoids the
failure a generic extractor has here: `trafilatura`'s image mode pulls the
related-article thumbnails from *outside* the container into the body.

Stdlib `html.parser` and nothing else. `lxml` is not installed in the API image
and `bs4` is only a transitive vnstock dependency; a body reader is not worth
promoting either into `requirements.txt`.

The HTTP posture is `cafef_rss`'s, reused rather than restated: the same browser
`User-Agent` (without it the WAF answers 503), the same timeout, and the same
`CafeFUnavailable` so an outage is still reported against the site that refused.
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from .cafef_rss import (
    CAFEF_USER_AGENT,
    FETCH_TIMEOUT_SECONDS,
    SOURCE_NAME,
    CafeFUnavailable,
)

logger = logging.getLogger(__name__)

# The container CafeF renders every story into. Matched on a class *token* so a
# sibling class (`detail-content afcbc-body`) still matches and a longer name
# that merely starts with it does not.
CONTENT_CLASS = "detail-content"

# Blocks that carry prose. Anything else at the top of the container — a `div`
# widget, a script, a stray `figcaption` — is furniture and is not emitted.
_PARAGRAPH_TAGS = frozenset({"p"})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4"})
_QUOTE_TAGS = frozenset({"blockquote"})
_LIST_TAGS = frozenset({"ul", "ol"})
_FIGURE_TAGS = frozenset({"figure"})
_BLOCK_TAGS = (
    _PARAGRAPH_TAGS | _HEADING_TAGS | _QUOTE_TAGS | _LIST_TAGS | _FIGURE_TAGS
)

# Their content is code or styling, never text a reader wants, and `html.parser`
# hands it over as ordinary character data unless it is skipped explicitly.
_OPAQUE_TAGS = frozenset({"script", "style", "noscript", "iframe"})

# HTML5 void elements: they never carry an end tag, so the depth counter must
# not wait for one.
_VOID_TAGS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
)

_WHITESPACE = re.compile(r"\s+")

# A caption CafeF renders as an empty `<figcaption>` placeholder, and the credit
# lines that are layout rather than description.
_MIN_CAPTION_CHARS = 3

# Below this a "block" is a stray label, a share prompt, or a leftover colon —
# never a sentence. Headings are exempt; they are short by design.
_MIN_PARAGRAPH_CHARS = 12

# An article this short did not extract; the container was renamed or the page
# was an interstitial. Better to raise than to serve a reader two sentences and
# call it the body.
MIN_ARTICLE_CHARS = 200

CAFEF_HOSTS = frozenset({"cafef.vn", "www.cafef.vn"})


def is_cafef_article_url(url: str) -> bool:
    """Whether this URL is a CafeF article this reader is allowed to fetch.

    The endpoint in front takes the URL from the client, which makes an
    unchecked fetch an open proxy into whatever the caller names. Scheme, host
    and CafeF's own `.chn` article suffix are all required; nothing else is
    reachable through this module.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and parsed.hostname.lower() in CAFEF_HOSTS
        and parsed.path.lower().endswith(".chn")
    )


def fetch_article(url: str) -> Mapping[str, Any]:
    """Read one CafeF story: its blocks, and the same text flattened.

    Raises `ValueError` for a URL this reader does not serve — a caller's
    mistake — and `CafeFUnavailable` for anything the site or the page did,
    including a page whose body did not survive extraction.
    """
    if not is_cafef_article_url(url):
        raise ValueError(f"Not a fetchable CafeF article URL: {url}")

    try:
        response = httpx.get(
            url,
            headers={"User-Agent": CAFEF_USER_AGENT},
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CafeFUnavailable(f"CafeF article request failed for {url}: {exc}") from exc

    blocks = extract_blocks(response.text)
    content = blocks_to_text(blocks)
    if len(content) < MIN_ARTICLE_CHARS:
        raise CafeFUnavailable(
            f"CafeF article at {url} yielded {len(content)} characters of body; "
            "the content container was probably renamed"
        )

    logger.info("CafeF article %s: %d blocks, %d chars", url, len(blocks), len(content))
    return {
        "url": url,
        "source": SOURCE_NAME,
        "blocks": blocks,
        "content": content,
    }


def extract_blocks(markup: str) -> list[dict[str, Any]]:
    """The article's blocks in reading order, or an empty list if none matched."""
    parser = _ArticleParser()
    parser.feed(markup)
    parser.close()
    return parser.blocks


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """The same article as newline-separated plain text.

    The flat form the rest of the platform already speaks: `NewsItem.content` is
    declared as stripped plain text, and the agent's grounding lane reads prose,
    not a block tree. Images contribute their caption, which is the only part of
    them that is text.
    """
    lines: list[str] = []
    for block in blocks:
        kind = block["kind"]
        if kind == "list":
            lines.extend(block["items"])
        elif kind == "image":
            if block.get("caption"):
                lines.append(block["caption"])
        elif block.get("text"):
            lines.append(block["text"])
    return "\n".join(lines)


class _ArticleParser(HTMLParser):
    """Emit the allowlisted blocks sitting directly inside `div.detail-content`.

    Depth is counted from the container, and only depth 1 opens a block, which
    is what separates prose from the widget `div`s that share the container. A
    `<p>` nested three levels down inside "TIN MỚI" is never reached, so no list
    of widget class names has to be kept current.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []

        # None until the container opens; then the nesting depth inside it.
        self._depth: int | None = None
        # Tag stack inside the container, so an unbalanced inner tag cannot
        # close the container early.
        self._open_tags: list[str] = []

        self._block: dict[str, Any] | None = None
        self._buffer: list[str] = []
        self._list_items: list[str] | None = None
        self._in_list_item = False
        self._in_caption = False
        self._opaque: str | None = None

    # -- container tracking --------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._opaque is not None:
            return
        if tag in _OPAQUE_TAGS:
            self._opaque = tag
            return

        if self._depth is None:
            if tag == "div" and _has_class(attrs, CONTENT_CLASS):
                self._depth = 0
                self._open_tags = []
            return

        if tag in _VOID_TAGS:
            self._handle_void(tag, attrs)
            return

        self._open_tags.append(tag)
        self._depth += 1
        self._on_open(tag, self._depth)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._opaque is not None or self._depth is None:
            return
        self._handle_void(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._opaque is not None:
            if tag == self._opaque:
                self._opaque = None
            return
        if self._depth is None or tag in _VOID_TAGS:
            return

        if self._depth == 0:
            # Nothing is open inside the container, so a `</div>` here is the
            # container's own. Any other tag is a stray close from malformed
            # markup and is ignored rather than allowed to end the article.
            if tag == "div":
                self._flush()
                self._depth = None
            return

        # Unwind to the matching open tag. CafeF's markup closes cleanly in the
        # pages measured, but an unbalanced inner tag must not shift the depth
        # counter permanently and silence every block after it.
        if tag not in self._open_tags:
            return
        while self._open_tags:
            popped = self._open_tags.pop()
            self._on_close(popped, self._depth)
            self._depth -= 1
            if popped == tag:
                break

    # -- block assembly ------------------------------------------------------

    def _on_open(self, tag: str, depth: int) -> None:
        if depth == 1 and tag in _BLOCK_TAGS:
            self._flush()
            self._begin(tag)
            return
        if self._block is None:
            return
        if tag == "li" and self._list_items is not None:
            self._in_list_item = True
            self._buffer = []
        elif tag == "figcaption" and self._block["kind"] == "image":
            self._in_caption = True
            self._buffer = []
        elif tag == "br":
            self._buffer.append(" ")

    def _on_close(self, tag: str, depth: int) -> None:
        if self._block is None:
            return
        if tag == "li" and self._in_list_item:
            text = _clean(self._buffer)
            if text:
                assert self._list_items is not None
                self._list_items.append(text)
            self._buffer = []
            self._in_list_item = False
        elif tag == "figcaption" and self._in_caption:
            caption = _clean(self._buffer)
            if len(caption) >= _MIN_CAPTION_CHARS:
                self._block["caption"] = caption
            self._buffer = []
            self._in_caption = False
        elif depth == 1:
            self._flush()

    def _begin(self, tag: str) -> None:
        self._buffer = []
        self._list_items = None
        if tag in _FIGURE_TAGS:
            self._block = {"kind": "image", "image_url": None, "caption": None}
        elif tag in _LIST_TAGS:
            self._list_items = []
            self._block = {"kind": "list", "items": self._list_items}
        elif tag in _HEADING_TAGS:
            self._block = {"kind": "heading", "text": None}
        elif tag in _QUOTE_TAGS:
            self._block = {"kind": "quote", "text": None}
        else:
            self._block = {"kind": "paragraph", "text": None}

    def _flush(self) -> None:
        """Close the open block, keeping it only if it carries something."""
        block = self._block
        self._block = None
        self._in_list_item = False
        self._in_caption = False
        items = self._list_items
        self._list_items = None
        buffered = self._buffer
        self._buffer = []

        if block is None:
            return

        kind = block["kind"]
        if kind == "list":
            if items:
                self.blocks.append({"kind": "list", "items": items})
            return
        if kind == "image":
            # A figure whose image did not resolve is a caption with nothing to
            # caption; the prose around it already stands on its own.
            if block["image_url"]:
                self.blocks.append(block)
            return

        text = _clean(buffered)
        floor = 1 if kind == "heading" else _MIN_PARAGRAPH_CHARS
        if len(text) >= floor:
            block["text"] = text
            self.blocks.append(block)

    def _handle_void(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and self._block is not None:
            self._buffer.append(" ")
            return
        if tag != "img" or self._block is None or self._block["kind"] != "image":
            return
        if self._block["image_url"] is None:
            self._block["image_url"] = _image_source(attrs)

    def handle_data(self, data: str) -> None:
        if self._opaque is None and self._block is not None:
            self._buffer.append(data)


def _has_class(attrs: list[tuple[str, str | None]], wanted: str) -> bool:
    """Whether `class` carries `wanted` as a whole token."""
    for name, value in attrs:
        if name == "class" and value:
            return wanted in value.split()
    return False


def _image_source(attrs: list[tuple[str, str | None]]) -> str | None:
    """The image's absolute URL, preferring `src` over the lazy-load attributes.

    Only http(s): a `data:` placeholder is what lazy loading puts in `src` while
    the real URL waits in `data-src`, and rendering the placeholder would draw a
    grey rectangle where the photo belongs.
    """
    found = {name: value for name, value in attrs if value}
    for attribute in ("src", "data-src", "data-original"):
        value = (found.get(attribute) or "").strip()
        if value.startswith(("https://", "http://")):
            return value
    return None


def _clean(buffer: list[str]) -> str:
    """Collapsed, entity-decoded text out of a block's accumulated character data."""
    text = html.unescape("".join(buffer))
    # A zero-width no-break space is CafeF's own padding inside sentences; left
    # in, it splits words for anything that later measures or searches the text.
    text = text.replace("﻿", "").replace("​", "")
    return _WHITESPACE.sub(" ", text).strip()
