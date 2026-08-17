"""What the open-web lane is allowed to say about itself while a Turn runs.

``docs/adr/0020`` narrows ADR-0013's "never a tool name, argument or result" rule
to the lanes it was written for. The store lane still publishes a bare phase; the
open web publishes the sentence it searched for and the pages it found, because
both are public and a reader who cannot see them cannot tell a company filing from
an anonymous aggregator.

Everything here is a projection of tool calls and tool results into that narrow
shape. Nothing reads a store field, and nothing carries a tool name onto the wire:
the tool names below are read to *decide* what a call was, and are dropped from
what comes out.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

#: The two tools whose work is public by nature and may describe itself.
#:
#: ``search_news`` is deliberately absent even though it is also external: its
#: argument is a Universe symbol rather than a sentence, and its items carry a
#: source name with no URL. There is nothing to link to and nothing a chip could
#: honestly say, so it keeps the bare phase ADR-0013 gave it.
WEB_SEARCH_TOOL = "web_search"
FETCH_URL_TOOL = "fetch_url"
DISCLOSING_TOOLS = frozenset({WEB_SEARCH_TOOL, FETCH_URL_TOOL})

#: What one activity event may carry, so a long round cannot become a page of chips.
MAX_QUERIES = 6
MAX_SOURCES = 12
MAX_TITLE_CHARS = 240
#: A snippet is a preview under the title in the source drawer, not the page.
MAX_SNIPPET_CHARS = 280


@dataclass(frozen=True)
class ProgressSource:
    """One page the Turn actually looked at, as the reader sees it listed.

    ``snippet``, ``published_at`` and ``retrieved_at`` are what the search result
    itself said about the page — an excerpt and two timestamps, all public, all
    already shown by the search engine that returned them. They ride along so the
    source drawer can say *what* a page claims and *when*, and they are optional
    on the wire because a ``fetch_url`` row has no excerpt to offer.
    """

    title: str
    url: str
    domain: str
    snippet: str = ""
    published_at: str | None = None
    retrieved_at: str | None = None

    def as_wire(self) -> dict[str, Any]:
        wire: dict[str, Any] = {"title": self.title, "url": self.url, "domain": self.domain}
        if self.snippet:
            wire["snippet"] = self.snippet
        if self.published_at:
            wire["published_at"] = self.published_at
        if self.retrieved_at:
            wire["retrieved_at"] = self.retrieved_at
        return wire


def domain_of(url: str) -> str:
    """The host a URL points at, or an empty string if it points nowhere.

    Resolved here rather than in the browser so the label under a source is the
    host the backend fetched, not one a renderer guessed from a string.
    """
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def queries_of(calls: Iterable[Any]) -> tuple[str, ...]:
    """The sentences an open-web round is about to ask, in call order.

    Read from the *arguments* of the calls the model just made, before they run:
    a chip that appeared only after the search returned would be a label for work
    the reader already watched finish.
    """
    queries: list[str] = []
    for call in calls:
        name = getattr(call, "name", None)
        arguments = getattr(call, "arguments", None)
        if name not in DISCLOSING_TOOLS or not isinstance(arguments, Mapping):
            continue
        raw = arguments.get("query") if name != FETCH_URL_TOOL else arguments.get("url")
        text = str(raw or "").strip()
        if text and text not in queries:
            queries.append(text)
        if len(queries) >= MAX_QUERIES:
            break
    return tuple(queries)


def sources_of(name: str, result: Mapping[str, Any]) -> tuple[ProgressSource, ...]:
    """Every page one open-web tool result stands on.

    Shapes differ by tool and are read defensively rather than trusted: a result
    that came back malformed should cost the trail one entry, never the Turn.
    """
    if name not in DISCLOSING_TOOLS or not isinstance(result, Mapping):
        return ()
    if name == FETCH_URL_TOOL:
        claim = result.get("external_claim")
        if not isinstance(claim, Mapping):
            return ()
        url = str(claim.get("source_url") or result.get("url") or "")
        return _sources(
            [{"title": claim.get("title"), "url": url, "retrieved_at": claim.get("retrieved_at")}]
        )
    rows = result.get("results")
    return _sources(rows if isinstance(rows, Sequence) else ())


def _sources(rows: Iterable[Any]) -> tuple[ProgressSource, ...]:
    found: list[ProgressSource] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        domain = domain_of(url)
        title = str(row.get("title") or "").strip()[:MAX_TITLE_CHARS]
        found.append(
            ProgressSource(
                title=title or domain or url,
                url=url,
                domain=domain,
                snippet=str(row.get("snippet") or "").strip()[:MAX_SNIPPET_CHARS],
                published_at=_timestamp(row.get("published_at")),
                retrieved_at=_timestamp(row.get("retrieved_at")),
            )
        )
    return tuple(found)


def _timestamp(raw: Any) -> str | None:
    """A timestamp as the string it arrived as, or nothing — never a coerced blank."""
    text = str(raw or "").strip()
    return text or None


def merge_sources(
    existing: Sequence[ProgressSource],
    incoming: Iterable[ProgressSource],
) -> tuple[ProgressSource, ...]:
    """Add what a round found to what the Turn already had, once each.

    Deduplicated by URL: two searches over one question routinely return the same
    company page, and a trail that listed it twice would inflate the count the
    reader is being asked to trust.
    """
    merged = list(existing)
    seen = {source.url for source in merged}
    for source in incoming:
        if source.url in seen:
            continue
        seen.add(source.url)
        merged.append(source)
    return tuple(merged[:MAX_SOURCES])


def searching_detail(queries: Sequence[str]) -> dict[str, Any] | None:
    """The ``detail`` a ``searching`` activity carries, or nothing to add."""
    if not queries:
        return None
    return {"queries": list(queries[:MAX_QUERIES])}


def found_detail(
    sources: Sequence[ProgressSource], result_count: int
) -> dict[str, Any] | None:
    """The ``detail`` a ``found_sources`` activity carries, or nothing to add.

    ``result_count`` is what the round actually returned, which is not the length
    of ``sources``: the list is capped and deduplicated for display, and the count
    is the honest number behind it.
    """
    if not sources:
        return None
    return {
        "result_count": result_count,
        "sources": [source.as_wire() for source in sources[:MAX_SOURCES]],
    }


__all__ = [
    "DISCLOSING_TOOLS",
    "FETCH_URL_TOOL",
    "MAX_QUERIES",
    "MAX_SNIPPET_CHARS",
    "MAX_SOURCES",
    "WEB_SEARCH_TOOL",
    "ProgressSource",
    "domain_of",
    "found_detail",
    "merge_sources",
    "queries_of",
    "searching_detail",
    "sources_of",
]
