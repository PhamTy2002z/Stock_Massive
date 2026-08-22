"""Server-fetched favicons for domains that show up in ``web_search`` results.

The UI wants a real logo next to each search result instead of a lettered
chip, and the browser must never be the one that fetches it: asking the
browser to load ``https://some-random-domain.example/favicon.ico`` directly
would tell that domain — and anything on the network path to it — which page
a signed-in user is reading, plus their IP address. So this fetches once, from
the server, through the exact same public-URL guard ``fetch_url`` uses
(``validate_public_url`` in ``agent/tools/web.py``, reused rather than
reimplemented), and caches both the hit and the miss so that a domain search
results keep repeating does not turn into a repeated outbound request.

Two outcomes only, and both are cacheable facts about a domain: it has a
fetchable ``/favicon.ico`` that is actually an image, or it does not. A miss is
not an error — most sites have no ``/favicon.ico`` — so it is cached for a day
and answered with 404, letting the UI's letter-chip fallback do its job
without the server re-fetching on every render.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import re
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.agent.tools.web import Resolver, _http_download, validate_public_url
from src.auth.dependencies import CurrentUser
from src.core.config import Settings, get_settings
from src.core.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets", tags=["assets"])

FAVICON_TIMEOUT_SECONDS = 3.0
#: How large an icon may be before it is refused.
#:
#: Measured rather than guessed: a real Vietnamese news site was found serving a
#: perfectly ordinary favicon at 103 KB, because a ``.ico`` is a container and
#: sites pack every resolution from 16px to 256px into one file. A 64 KB ceiling
#: rejected it and the reader saw two grey letters for a site that had a logo
#: all along. The cost of the higher ceiling is paid once per domain per week,
#: because the answer is cached either way.
FAVICON_MAX_BYTES = 256 * 1024
#: How large a home page may be before the icon hunt gives up on it.
#:
#: Only the ``<head>`` is wanted, but the reader underneath refuses an oversized
#: response rather than truncating it — correct for its own job, feeding a page
#: to the model, and unhelpful here. So the ceiling has to clear a whole home
#: page instead of a head: measured, Vietnamese news front pages run 200–400 KB,
#: and a 192 KB ceiling silently lost every one of them. A megabyte clears them
#: with room to spare, and is paid at most once per domain per week — only for a
#: domain whose ``/favicon.ico`` already failed, and never twice, because the
#: outcome is cached whichever way it goes.
FAVICON_PAGE_MAX_BYTES = 1024 * 1024
FAVICON_MAX_REDIRECTS = 2
FAVICON_SUCCESS_TTL_SECONDS = 7 * 24 * 60 * 60
FAVICON_FAILURE_TTL_SECONDS = 24 * 60 * 60
FAVICON_SUCCESS_CACHE_CONTROL = "public, max-age=604800, immutable"
FAVICON_FAILURE_CACHE_CONTROL = "public, max-age=86400"

_CACHE_KEY_PREFIX = "stock_massive:favicon"
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Only letters, digits, dots and hyphens: no scheme, path, port, credentials or
# whitespace can survive this allowlist, so the string never has to go through
# ``urlsplit`` to be judged — that parser is exactly what lets a scheme, a
# path or an ``@`` change what a downstream check believes the host is.
_HOSTNAME_ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9.-]+$")

#: The ``rel`` values that name a site's icon, lower-cased.
#:
#: ``rel`` is a space-separated token list, so this is matched token by token
#: rather than by substring: ``rel="icon"`` and ``rel="shortcut icon"`` both
#: qualify, while ``rel="apple-touch-icon-precomposed"`` is matched only by its
#: own token and never by containing the word *icon*.
_ICON_REL_TOKENS = frozenset(
    {"icon", "shortcut", "apple-touch-icon", "apple-touch-icon-precomposed"}
)


def _content_type_of(headers: Mapping[str, str]) -> str:
    """The bare media type, lower-cased, with any parameters dropped."""
    raw = headers.get("content-type") or headers.get("Content-Type") or ""
    return raw.split(";", 1)[0].strip().lower()


class _IconLinkParser(HTMLParser):
    """The first icon a page declares, and nothing else about the page.

    Stops at ``</head>``. Everything that declares an icon does so in the head,
    and a parser that read on would spend its time on the body of a news site
    for no possible gain.

    First match wins rather than best match: choosing between a 16px and a 180px
    declaration would mean parsing ``sizes``, and the two are equally usable at
    the 19 pixels this is drawn at.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.href: str | None = None
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done or tag.lower() != "link":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        rel = {token for token in values.get("rel", "").lower().split() if token}
        if not rel & _ICON_REL_TOKENS:
            return
        href = values.get("href", "").strip()
        if href:
            self.href = href
            self._done = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "head":
            self._done = True

Download = Callable[[str, int, float], tuple[int, Mapping[str, str], bytes]]


def validate_domain(raw: str) -> str:
    """A plain hostname, lowercased, or the reason it is rejected.

    Deliberately not a URL parser: accepting anything ``urlsplit`` can make
    sense of is how a scheme, a path, a port or an ``@`` sneaks past a check
    that only meant to look at the host.
    """
    if not raw:
        raise ValueError("domain is required")
    if len(raw) > 253:
        raise ValueError("domain must be at most 253 characters")
    if not _HOSTNAME_ALLOWED_CHARS.fullmatch(raw):
        raise ValueError("domain must contain only letters, digits, dots and hyphens")
    if "." not in raw:
        raise ValueError("domain must contain at least one dot")
    return raw.lower()


@dataclass(frozen=True)
class FaviconResult:
    """One favicon lookup outcome: bytes and their type, or nothing found."""

    found: bool
    content_type: str | None = None
    body: bytes | None = None


class FaviconTools:
    """Fetch one domain's favicon behind the same guard as ``fetch_url``.

    ``download`` defaults to the DNS-pinned downloader ``fetch_url`` itself
    uses, so a favicon fetch gets the same rebind protection: the address
    that was validated is the address the socket connects to, not whatever a
    second DNS answer might say a moment later.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        redis_factory: Callable[[], Any] | None = None,
        resolver: Resolver = socket.getaddrinfo,
        download: Download | None = None,
    ) -> None:
        self._injected_settings = settings
        self._redis_factory = redis_factory or get_redis
        self._resolver = resolver
        self._download = download or self._default_download

    @property
    def _settings(self) -> Settings:
        return self._injected_settings or get_settings()

    def _default_download(
        self, url: str, max_bytes: int, timeout: float
    ) -> tuple[int, Mapping[str, str], bytes]:
        return _http_download(url, max_bytes, timeout, resolver=self._resolver)

    def _denylist(self) -> tuple[str, ...]:
        return tuple(self._settings.web_domain_denylist.split(","))

    def serve(self, domain: str) -> Response:
        """The HTTP response for one already-format-validated domain."""
        redis = self._redis_factory()
        cached = self._load_cache(redis, domain) if redis is not None else None
        result = cached if cached is not None else self._fetch(domain)
        if cached is None and redis is not None:
            self._store_cache(redis, domain, result)
        if not result.found:
            return Response(
                status_code=404,
                content=b"",
                headers={"Cache-Control": FAVICON_FAILURE_CACHE_CONTROL},
            )
        return Response(
            content=result.body,
            media_type=result.content_type,
            headers={"Cache-Control": FAVICON_SUCCESS_CACHE_CONTROL},
        )

    def _fetch(self, domain: str) -> FaviconResult:
        """This domain's icon, by the two routes a site can offer one.

        ``/favicon.ico`` first, because it costs one request and most sites
        still honour it. When that comes back empty — a 404, an HTML error page,
        anything that is not an image — the home page is read for a
        ``<link rel="icon">``, which is where a site that has moved its icon to
        a CDN or a hashed filename declares it. Measured: a listed company's
        site answered ``/favicon.ico`` with a 404 page while declaring a
        perfectly good icon in its markup.

        The second route is only ever taken after the first fails, so an
        ordinary domain still costs one request, and a domain with no icon at
        all costs two — once a week, because the failure is cached too.
        """
        direct = self._download_icon(f"https://{domain}/favicon.ico")
        if direct.found:
            return direct
        declared = self._declared_icon_url(domain)
        if declared is None:
            return FaviconResult(found=False)
        return self._download_icon(declared)

    def _declared_icon_url(self, domain: str) -> str | None:
        """The icon a home page declares in its markup, as an absolute URL."""
        page = self._read(f"https://{domain}/", FAVICON_PAGE_MAX_BYTES)
        if page is None:
            return None
        url, headers, body = page
        content_type = _content_type_of(headers)
        if not content_type.startswith("text/html"):
            return None
        parser = _IconLinkParser()
        try:
            # ``errors="replace"`` rather than a guessed codec: this is being
            # scanned for one attribute, and a page whose encoding we got wrong
            # still yields a correct ASCII href.
            parser.feed(body.decode("utf-8", errors="replace"))
            parser.close()
        except Exception as exc:  # noqa: BLE001 - somebody else's markup
            logger.info("Favicon markup for %s could not be parsed: %s", domain, exc)
            return None
        # Resolved against the URL the page was actually served from, which is
        # not the one asked for when a redirect moved it.
        return urljoin(url, parser.href) if parser.href else None

    def _download_icon(self, url: str) -> FaviconResult:
        """Fetch one candidate icon URL, and judge what came back."""
        fetched = self._read(url, FAVICON_MAX_BYTES)
        if fetched is None:
            return FaviconResult(found=False)
        _, headers, body = fetched
        content_type = _content_type_of(headers)
        if not content_type.startswith("image/") or not body:
            return FaviconResult(found=False)
        return FaviconResult(found=True, content_type=content_type, body=body)

    def _read(
        self, url: str, max_bytes: int
    ) -> tuple[str, Mapping[str, str], bytes] | None:
        """One GET, re-validating every hop. ``None`` for anything but a 2xx."""
        denylist = self._denylist()
        current = url
        for redirect_count in range(FAVICON_MAX_REDIRECTS + 1):
            try:
                current = validate_public_url(
                    current, denylist=denylist, resolver=self._resolver
                )
            except ValueError as exc:
                logger.info("Favicon URL %s rejected: %s", current, exc)
                return None
            try:
                status, headers, body = self._download(
                    current, max_bytes, FAVICON_TIMEOUT_SECONDS
                )
            except (OSError, ValueError) as exc:
                logger.info("Favicon download of %s failed: %s", current, exc)
                return None
            if status in _REDIRECT_STATUSES:
                location = headers.get("location") or headers.get("Location")
                if not location or redirect_count == FAVICON_MAX_REDIRECTS:
                    return None
                current = urljoin(current, location)
                continue
            if not 200 <= status < 300:
                return None
            return current, headers, body
        return None

    @staticmethod
    def _cache_key(domain: str) -> str:
        return f"{_CACHE_KEY_PREFIX}:{domain}"

    def _load_cache(self, redis: Any, domain: str) -> FaviconResult | None:
        try:
            raw = redis.get(self._cache_key(domain))
        except Exception as exc:  # noqa: BLE001 - a cache outage must not block serving
            logger.warning("Favicon cache read failed for %s: %s", domain, exc)
            return None
        if not raw:
            return None
        try:
            record = json.loads(raw)
            if not record.get("found"):
                return FaviconResult(found=False)
            body = base64.b64decode(record["body_b64"])
            return FaviconResult(
                found=True, content_type=record["content_type"], body=body
            )
        except (TypeError, ValueError, KeyError, binascii.Error):
            logger.warning("Discarding an unreadable cached favicon record for %s", domain)
            return None

    def _store_cache(self, redis: Any, domain: str, result: FaviconResult) -> None:
        if result.found:
            assert result.body is not None and result.content_type is not None
            record: Mapping[str, Any] = {
                "found": True,
                "content_type": result.content_type,
                "body_b64": base64.b64encode(result.body).decode("ascii"),
            }
            ttl = FAVICON_SUCCESS_TTL_SECONDS
        else:
            record = {"found": False}
            ttl = FAVICON_FAILURE_TTL_SECONDS
        try:
            redis.set(self._cache_key(domain), json.dumps(record), ex=ttl)
        except Exception as exc:  # noqa: BLE001 - caching is an optimization, not a contract
            logger.warning("Favicon cache write failed for %s: %s", domain, exc)


def get_favicon_tools() -> FaviconTools:
    return FaviconTools()


@router.get("/favicon")
async def get_favicon(
    _current_user: CurrentUser,
    domain: str = Query(..., min_length=1, max_length=253),
    tools: FaviconTools = Depends(get_favicon_tools),
) -> Response:
    """One domain's favicon, fetched and validated server-side.

    404 with an empty body is the correct answer for "no favicon there", not
    an error: the UI already falls back to a letter chip, and treating a
    common, harmless fact about a domain as a failure would just make the
    model or the browser retry into the same answer.
    """
    try:
        clean_domain = validate_domain(domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await asyncio.to_thread(tools.serve, clean_domain)


__all__ = [
    "FAVICON_FAILURE_CACHE_CONTROL",
    "FAVICON_FAILURE_TTL_SECONDS",
    "FAVICON_MAX_BYTES",
    "FAVICON_MAX_REDIRECTS",
    "FAVICON_SUCCESS_CACHE_CONTROL",
    "FAVICON_SUCCESS_TTL_SECONDS",
    "FaviconResult",
    "FaviconTools",
    "get_favicon_tools",
    "router",
    "validate_domain",
]
