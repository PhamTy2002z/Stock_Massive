"""CafeF RSS as the press-news source behind the market feed.

Why not VCI, which already backs the per-symbol lane: measured across FPT, STB
and VNM, all 50 rows per symbol carry `news_title`, `public_date` and
`news_image_url`, while `news_short_content`, `news_full_content`,
`news_source`, `news_source_link` and `news_sub_title` are 0/50 non-null. VCI
publishes corporate disclosures ("FPT: Nghị quyết HĐQT về..."), and its
`news_image_url` is the company logo rather than an article image — a reader
screen built on that frame has nothing to render.

A browser `User-Agent` is mandatory. With curl's default UA every CafeF URL
answers HTTP 503 from a WAF; with a desktop Chrome UA the same URL answers 200
with RSS 2.0. That header is the whole difference between a feed and an outage.

`https://cafef.vn/robots.txt` is `User-agent: * / Allow: /`, so polling the
public category feeds is within what the site invites.

Full article text is deliberately not fetched. The body is VCCorp's copyright;
the feed's own summary plus a link to the original is the honest surface, and it
also keeps a rebuild at one request per category.

Nothing here is a vnstock call: no quota layer meters it, and its failures raise
`CafeFUnavailable` rather than `VnstockUnavailable` so the outage is reported
against the site that actually refused.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from collections.abc import Mapping
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, NamedTuple
from xml.etree import ElementTree

import httpx

from .normalize import VN_TZ

logger = logging.getLogger(__name__)

CAFEF_RSS_BASE = "https://cafef.vn"

# Not cosmetic: without a browser UA the WAF answers 503 to every CafeF URL.
CAFEF_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

FETCH_TIMEOUT_SECONDS = 10

SOURCE_NAME = "CafeF"

# The summary is a card teaser. Anything longer is the article, which this path
# does not serve.
SUMMARY_LIMIT = 600

TITLE_LIMIT = 300


class CafeFCategory(NamedTuple):
    """One facet: the slug we publish, CafeF's path for it, its label."""

    slug: str
    path: str
    label: str


# Our slugs are the public contract; CafeF's paths stay an implementation detail
# behind this table, so an upstream rename is one edit here rather than a
# breaking change to the API. Order is the order the UI shows the facets in.
#
# The labels follow the reference product's own facet row, with two substitutions
# it could not survive: "Đọc nhiều" needs a read-count no source publishes, and
# CafeF has no retail feed (its `thi-truong` category is named "Thị trường" but
# carries property coverage). Chứng khoán and Doanh nghiệp take those two slots —
# on a market platform they are the facets a reader actually came for.
#
# Each label was checked against what the feed returns, not against its name:
# `vi-mo-dau-tu` is "Kinh tế vĩ mô - Đầu tư", `kinh-te-so` carries technology,
# and `tai-chinh-quoc-te` carries world coverage.
CAFEF_CATEGORIES: tuple[CafeFCategory, ...] = (
    CafeFCategory("moi-nhat", "home", "Mới nhất"),
    CafeFCategory("chung-khoan", "thi-truong-chung-khoan", "Chứng khoán"),
    CafeFCategory("kinh-te", "vi-mo-dau-tu", "Kinh tế"),
    CafeFCategory("tai-chinh", "tai-chinh-ngan-hang", "Tài chính"),
    CafeFCategory("bat-dong-san", "bat-dong-san", "Bất động sản"),
    CafeFCategory("doanh-nghiep", "doanh-nghiep", "Doanh nghiệp"),
    CafeFCategory("cong-nghe", "kinh-te-so", "Công nghệ"),
    CafeFCategory("the-gioi", "tai-chinh-quoc-te", "Thế giới"),
)

_CATEGORY_BY_SLUG = {category.slug: category for category in CAFEF_CATEGORIES}

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_IMG_SRC = re.compile(
    r"<img[^>]+\bsrc\s*=\s*[\"']?(https?://[^\"'\s>]+)", re.IGNORECASE
)
# Every CafeF slug ends with the article's own id: `-188260817190901375.chn`.
_ARTICLE_ID = re.compile(r"-(\d{6,})\.chn", re.IGNORECASE)

# RFC 822 with a two-digit year, which is what CafeF stamps:
# `Mon, 17 Aug 26 19:59:00 +0700`.
_PUBDATE_FORMAT = "%a, %d %b %y %H:%M:%S %z"


class CafeFUnavailable(RuntimeError):
    """CafeF did not answer with a feed this request could read.

    Distinct from `VnstockUnavailable`: no vnstock allowance is involved here,
    and the handler for that exception would name the wrong cause.
    """


def category_slugs() -> tuple[str, ...]:
    """The slugs this API exposes, in display order."""
    return tuple(category.slug for category in CAFEF_CATEGORIES)


def fetch_category(slug: str) -> tuple[Mapping[str, Any], ...]:
    """Read one category feed, one HTTP request, in the order CafeF served it.

    Raises `ValueError` for a slug this API does not expose — a caller's
    mistake, not an outage — and `CafeFUnavailable` for anything the site did.
    """
    category = _CATEGORY_BY_SLUG.get(slug)
    if category is None:
        raise ValueError(f"Unknown CafeF news category: {slug}")

    url = f"{CAFEF_RSS_BASE}/{category.path}.rss"
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": CAFEF_USER_AGENT},
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CafeFUnavailable(f"CafeF RSS request failed for {slug}: {exc}") from exc

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise CafeFUnavailable(
            f"CafeF RSS for {slug} was not parseable XML: {exc}"
        ) from exc

    items = tuple(
        row
        for row in (_read_item(element, slug) for element in root.iter("item"))
        if row is not None
    )
    logger.info("CafeF %s returned %d items", slug, len(items))
    return items


def _read_item(element: ElementTree.Element, slug: str) -> Mapping[str, Any] | None:
    """Normalize one `<item>`, or None if it is not an article a reader can open."""
    title = _plain_text(_child_text(element, "title"), TITLE_LIMIT)
    link = _absolute_link(_child_text(element, "link"))
    if not title or not link:
        return None

    description = _child_text(element, "description") or ""
    return {
        "id": _article_id(_child_text(element, "guid") or link),
        "title": title,
        "url": link,
        "summary": _plain_text(description, SUMMARY_LIMIT),
        "image_url": _first_image(description),
        "published_at": _published_at(_child_text(element, "pubDate")),
        "source": SOURCE_NAME,
        "category": slug,
    }


def _child_text(element: ElementTree.Element, tag: str) -> str | None:
    child = element.find(tag)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _article_id(identity: str) -> str:
    """A stable per-article id, never a position in the feed.

    CafeF's own article id is the digit run its slug ends with, which survives
    the feed shifting under a client. When the pattern is absent the link itself
    is the identity, hashed to keep the id short and URL-safe.
    """
    match = _ARTICLE_ID.search(identity)
    if match:
        return match.group(1)
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]


def _plain_text(value: str | None, limit: int) -> str | None:
    """Readable text out of a description that carries markup and entities.

    Tags are stripped before entities are unescaped, so an escaped `&lt;p&gt;`
    in the prose cannot become a tag that the strip already walked past.
    """
    if value is None:
        return None
    text = _HTML_TAG.sub(" ", value)
    text = html.unescape(text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:limit] if text else None


def _first_image(description: str) -> str | None:
    """The article thumbnail CafeF opens its description with, if it has one."""
    match = _IMG_SRC.search(description)
    return match.group(1) if match else None


def _absolute_link(value: str | None) -> str | None:
    """http(s) only — a relative path is useless to a client that just opens it."""
    if value is None:
        return None
    text = value.strip()
    return text if text.startswith(("http://", "https://")) else None


def _published_at(raw: str | None) -> str:
    """ISO stamp in `Asia/Ho_Chi_Minh`, or "" when the item carries no date.

    CafeF writes a two-digit year, so the format is RFC 822 with `%y`. Parsing
    goes through `parsedate_to_datetime` first because it reads the English
    weekday and month names without depending on the process locale, which
    `strptime`'s `%a`/`%b` do.
    """
    if not raw:
        return ""

    text = raw.strip()
    parsed: datetime | None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = None

    if parsed is None:
        try:
            parsed = datetime.strptime(text, _PUBDATE_FORMAT)
        except ValueError:
            return ""

    if parsed.tzinfo is None:
        # A stamp with no offset is Vietnamese wall time; that is the only zone
        # this feed publishes in.
        parsed = parsed.replace(tzinfo=VN_TZ)
    return parsed.astimezone(VN_TZ).isoformat()
