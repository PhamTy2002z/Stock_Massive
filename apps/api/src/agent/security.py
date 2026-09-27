"""Egress guards shared by outbound web calls and durable tool traces."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from src.core.llm.errors import REDACTED, redact

from .threat_patterns import normalise

_SENSITIVE_FIELD = re.compile(
    r"(?i)^(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|client[_-]?secret|secret|password|passwd|key|token|"
    r"session|auth)$"
)


class SecretEgressBlocked(ValueError):
    """Credential-shaped data was refused before outbound I/O."""


def redact_trace_value(value: Any, *, field: str | None = None) -> Any:
    """Recursively remove credential values from the durable trace projection."""

    if field is not None and _SENSITIVE_FIELD.fullmatch(str(field)):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(key): redact_trace_value(item, field=str(key))
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_trace_value(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def contains_secret(text: str) -> bool:
    """Whether outbound text contains a credential, including encoded forms."""

    raw = str(text or "")
    folded = normalise(unquote(raw))
    if redact(folded) != folded:
        return True
    parsed = urlsplit(folded)
    return any(
        _SENSITIVE_FIELD.fullmatch(name) and bool(value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
    )


def refuse_secret_egress(text: str, *, label: str) -> None:
    """Fail before provider, DNS or socket I/O without echoing the secret."""

    if contains_secret(text):
        raise SecretEgressBlocked(
            f"{label} contains credential-shaped data and was refused"
        )


#: The argument that names the destination, for every tool that sends a request
#: to a URL the model chose. A search query is deliberately absent: it goes to
#: one fixed provider, and a query is what searching is.
URL_EGRESS_ARGUMENTS: Mapping[str, str] = {"fetch_url": "url"}

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'`\\]+", re.IGNORECASE)
_URL_TRAILING = ".,;:!?)]}'\""


def normalise_url(url: str) -> str | None:
    """The comparable form of an http(s) URL, or ``None`` when it is not one.

    Scheme and authority are case-insensitive and the fragment never leaves the
    browser, so those are folded; path and query are compared as written.
    """
    try:
        parts = urlsplit(str(url).strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


def urls_in(text: str) -> set[str]:
    """Every http(s) URL written in ``text``, normalised."""
    found: set[str] = set()
    for match in _URL_IN_TEXT.finditer(str(text or "")):
        normalised = normalise_url(match.group(0).rstrip(_URL_TRAILING))
        if normalised is not None:
            found.add(normalised)
    return found


def _search_result_urls(result: Mapping[str, Any]) -> Iterable[Any]:
    for item in result.get("results") or ():
        if isinstance(item, Mapping):
            yield item.get("url")


def _page_urls(result: Mapping[str, Any]) -> Iterable[Any]:
    # Where the page was actually read from (redirects included), what it says
    # its own address is, and the links written in its visible text.
    yield result.get("url")
    yield result.get("canonical_url")
    yield from urls_in(str(result.get("content") or ""))


#: Where each tool's result names a source's own URL. Only these fields seed the
#: URLs a tainted Turn may follow: a tool that echoes the model's argument back
#: (a search query, a recall filter) would otherwise launder a composed URL into
#: one that looks like a result wrote it.
SOURCE_URL_FIELDS: Mapping[str, Callable[[Mapping[str, Any]], Iterable[Any]]] = {
    "web_search": _search_result_urls,
    "fetch_url": _page_urls,
}


def source_urls(
    tool_name: str, result: Any, arguments: Mapping[str, Any]
) -> set[str]:
    """The URLs a tool result wrote as sources, minus any the call itself sent.

    A URL that appears in the call's own arguments was the model's, whatever
    the result says; it never becomes a URL "a source wrote".
    """
    extract = SOURCE_URL_FIELDS.get(tool_name)
    if extract is None or not isinstance(result, Mapping):
        return set()
    found = {
        normalised
        for value in extract(result)
        if isinstance(value, str) and (normalised := normalise_url(value)) is not None
    }
    sent: set[str] = set()
    for value in arguments.values():
        if isinstance(value, str):
            sent |= urls_in(value)
            if (normalised := normalise_url(value)) is not None:
                sent.add(normalised)
    return found - sent


def tainted_egress_refusal(url: str, *, seen: Collection[str]) -> str | None:
    """Why a URL may not be requested once a Turn has read untrusted content.

    After a stranger's text is in the context, a URL the model *composes* is a
    channel out: a page can ask for ``https://attacker/<what the user said>`` in
    the query, the path or a subdomain alike. So once tainted, only a URL
    written verbatim by the user's message or by a source this Turn read
    (a search result, a page's address or its links) may be requested; the
    comparison folds scheme, host and fragment and nothing else.
    """
    normalised = normalise_url(url)
    if normalised is not None and normalised in seen:
        return None
    return (
        "This URL was not requested: this turn has already read untrusted "
        "content, and neither the user's message nor a search result or page "
        "read in this turn gave this exact URL. Fetch a URL exactly as a "
        "web_search result or a page already read wrote it; do not build, "
        "shorten or edit one."
    )


#: Address blocks ``is_global`` calls public although traffic sent to them lands
#: on an address derived from the one embedded in them: NAT64 (well-known and
#: local-use), 6to4, and the deprecated IPv4-compatible block.
_TRANSLATED_V6 = tuple(
    ipaddress.ip_network(block)
    for block in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "::/96")
)


def is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether a resolved address may be connected to on the model's behalf.

    ``is_global`` first, because a hand-written list of private ranges is a list
    that misses one. Then the cases it gets wrong: a mapped IPv4 address is
    judged as the IPv4 address it is, the translation blocks are refused
    whatever they embed, and multicast is refused because it is never a server.
    """
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped
        if mapped is not None:
            return is_public_address(mapped)
        if any(address in block for block in _TRANSLATED_V6):
            return False
    return address.is_global and not address.is_multicast


__all__ = [
    "SOURCE_URL_FIELDS",
    "URL_EGRESS_ARGUMENTS",
    "SecretEgressBlocked",
    "contains_secret",
    "is_public_address",
    "normalise_url",
    "redact_trace_value",
    "refuse_secret_egress",
    "source_urls",
    "tainted_egress_refusal",
    "urls_in",
]
