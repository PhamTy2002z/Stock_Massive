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


def _rows_of(name: str, result: Mapping[str, Any]) -> tuple[Any, ...]:
    """The rows one open-web tool result carries, in the order it carried them.

    The single place that knows each tool's shape. Position matters to one caller
    and not to the other — the trail lists pages, while a citation names the row
    it read — so both read the same sequence and differ only in what they keep of
    it. Shapes are read defensively rather than trusted: a result that came back
    malformed should cost the trail one entry, never the Turn.
    """
    if name not in DISCLOSING_TOOLS or not isinstance(result, Mapping):
        return ()
    if name == FETCH_URL_TOOL:
        claim = result.get("external_claim")
        if not isinstance(claim, Mapping):
            return ()
        url = str(claim.get("source_url") or result.get("url") or "")
        return (
            {
                "title": claim.get("title"),
                "url": url,
                "retrieved_at": claim.get("retrieved_at"),
            },
        )
    rows = result.get("results")
    return tuple(rows) if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)) else ()


def sources_of(name: str, result: Mapping[str, Any]) -> tuple[ProgressSource, ...]:
    """Every page one open-web tool result stands on."""
    return _sources(_rows_of(name, result))


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


def sources_by_call(calls: Iterable[Any]) -> dict[str, dict[int, str]]:
    """Which page each open-web call returned **at which position**, by call id.

    The inverse of :func:`sources_of`, and it exists for one reader: a released
    block cites tool calls by position — ``results.3.title`` — and a chip under
    that block has to name the page that row actually was. Built from the same
    row sequence as the trail, so the trail the reader watched and the chip under
    the sentence can never disagree about which page a claim came from.

    **Keyed by position rather than packed into a list**, because a row without a
    URL is dropped from the trail: packing the survivors would shift every later
    row's index by one and name the wrong page. A position with no URL is simply
    absent, and a citation of it names no page at all — which is the honest answer
    and, unlike a shifted index, an obviously empty one.

    Only the two disclosing tools appear. ``search_news`` is absent for the
    reason it is absent from :data:`DISCLOSING_TOOLS` — its items carry a source
    name and no URL, so there is nothing for a chip to link to.
    """
    index: dict[str, dict[int, str]] = {}
    for call in calls:
        name = str(getattr(call, "name", "") or "")
        call_id = str(getattr(call, "call_id", "") or "")
        result = getattr(call, "result", None)
        if not call_id or name not in DISCLOSING_TOOLS or not isinstance(result, Mapping):
            continue
        urls: dict[int, str] = {}
        for position, row in enumerate(_rows_of(name, result)):
            if not isinstance(row, Mapping):
                continue
            url = str(row.get("url") or "").strip()
            if url:
                urls[position] = url
        if urls:
            index[call_id] = urls
    return index


def _row_index(field_path: str) -> int | None:
    """Which result inside a call a reference points at, if it points at one.

    A search result is cited by its position — ``results.0.title`` — so the path
    itself says which page the claim came from. The first integer segment is that
    position; a path with none (a fetched page's own claim, a summary key) is
    about the call as a whole.
    """
    for part in field_path.split("."):
        if part.isdigit():
            return int(part)
    return None


def block_source_ids(
    references: Iterable[tuple[str, str]],
    index: Mapping[str, Mapping[int, str]],
    known: Iterable[str],
) -> tuple[str, ...]:
    """The pages one block's evidence rests on, in the order it cited them.

    A URL is the id, because a URL is already the identity the trail
    deduplicates by (:func:`merge_sources`) — an id invented here would be a
    second name for the same page, and the browser would have to be told how to
    map one to the other.

    Each reference is a call id and the field path inside that call's result, and
    the path is read rather than ignored: a search that returned twelve pages and
    a sentence citing the title of one of them are different claims, and naming
    all twelve under that sentence would tell the reader eleven pages agreed with
    something they were never asked about. A cited row whose page cannot be
    resolved therefore names nothing — never everything.

    **The one check is membership in this Turn's own source set.** This is
    display metadata and never a gate: ``docs/adr/0015`` puts every enforcement
    at the layer that can prove it, and "which page is behind this paragraph" has
    no consequence a reader can be harmed by getting an empty answer to. So a
    page the Turn did not actually list is dropped from the chips and the block
    is released exactly as it was.
    """
    allowed = frozenset(known)
    found: list[str] = []
    for call_id, field_path in references:
        urls = index.get(call_id) or {}
        row = _row_index(field_path)
        if row is None:
            # A reference to the call rather than to one of its rows — a fetched
            # page's own claim, or a summary key. It rests on everything that
            # call came back with.
            cited: tuple[str, ...] = tuple(urls[key] for key in sorted(urls))
        else:
            # A row the citation named. A position the result carried no URL for
            # names no page, rather than borrowing the next one's.
            page = urls.get(row)
            cited = (page,) if page else ()
        for url in cited:
            if url in allowed and url not in found:
                found.append(url)
    return tuple(found)


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
    "block_source_ids",
    "domain_of",
    "found_detail",
    "merge_sources",
    "queries_of",
    "searching_detail",
    "sources_by_call",
    "sources_of",
]
