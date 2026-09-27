"""Every figure an answer states, checked against what this Turn actually read.

The chart has always been the host's: ``visual.py`` draws only values a named
call returned, so "did the model invent this price" cannot be asked of it. The
prose had no such rule. On 2026-09-26 a light-lane Turn read STB's daily bars —
closing at 56.500 đồng on its last row — and answered "hiện tại 35.000–38.000
đồng", dated to a year that had already ended; nothing between the model and the
reader looked at a single number. This module is that look, applied to every
answer on every lane.

**What it decides, per figure.** Whether the number is printed in a source this
Turn read (a market row, a fetched page, a search snippet, a structured
statement or a calculation a tool returned), and *when* that source says it was
true. A figure is:

* ``grounded`` — found, and its source agrees with the time the sentence talks
  about. It is annotated in place with a citation and its date.
* ``stale`` — found only in a web source older than :data:`WEB_FRESH_DAYS`. It is
  annotated with its date and ``nguồn cũ``.
* ``unverified`` — not found, or found only in a source whose time contradicts
  the sentence: a line saying "tháng 9/2025" backed only by 2024 bars, or a line
  saying "hiện tại" backed only by a session older than the latest one read. It
  is annotated ``chưa kiểm chứng`` and never deleted (owner decision,
  2026-09-26): the reader sees what was said and that nothing backs it.

**Why literal, with a rounding allowance.** The ``numbers`` module explains the
trap: a page of two hundred numbers supports almost any number under arithmetic,
so a derivation check accepts fabrications at nearly the rate it accepts facts.
Here the figure must be printed in the source — as written, or rounded to the
precision the answer wrote it at (``111 nghìn tỷ`` for ``111.228 tỷ``,
``56,5 nghìn`` for ``56.500 đồng``). A self-computed growth rate is therefore
unverified until a calculation tool prints it, which is the intended pressure.

**What it cannot see.** A fabricated figure that happens to equal a real one in
a long source still matches; the period rule narrows that for dated sources, and
nothing here pretends to close it. Numbers the reader wrote in their own question,
or that come back from their own memory, are theirs and are not labelled.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

from ..messages import ToolCallStatus, TurnToolCall
from . import numbers
from .contracts import (
    ClaimKind,
    ClaimLedger,
    EvidenceKind,
    EvidenceRef,
    PublicationConfidence,
    PublicationMethod,
    SourceClass,
    TimePrecision,
    TosRisk,
    VerificationVerdict,
    VerifiedClaim,
    VerifierOutcome,
    build_evidence_ref,
)
from .source_policy import POLICY_VERSION, canonical_url

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

#: Written into every ledger this module builds. The deep pipeline's ledgers say
#: ``"1"``; this one says what produced it, so a reader of the table can tell a
#: verifier's ledger from a figure check's.
LEDGER_VERSION = "grounding-1"

#: How old a web source may be before a figure resting on it is called stale.
#: A quarter of reporting plus the weeks a filing takes to appear: a bank's
#: ratios from a page older than this describe a period that a newer filing has
#: already replaced.
WEB_FRESH_DAYS = 120

#: How old a news item may be before a figure resting on it is called stale.
NEWS_FRESH_DAYS = 30

#: How old the latest session read may be before "hiện tại" can no longer rest
#: on it. A week covers Tết and the long holidays; past it, "now" is not a word
#: the data supports.
CURRENT_SESSION_DAYS = 7

#: The most figures one repair note lists. A draft with more than this many
#: unsupported figures is not going to be fixed figure by figure, and the note's
#: last line says to rewrite from the data instead.
MAX_REPAIR_ITEMS = 20

#: The tools whose results are the reader's own words. A figure found there is
#: not a claim about the market; it is the reader's number, repeated.
EXEMPT_TOOLS = frozenset({"session_search", "recall_facts"})

MARKET_TOOL = "get_market_data"
PAGE_TOOL = "fetch_url"
SEARCH_TOOL = "web_search"
#: A user connector's tools (``src/connectors/``): named ``mcp__…`` when
#: preloaded, or reached through the on-demand envelope.
CONNECTOR_PREFIX = "mcp__"
CONNECTOR_CALL_TOOL = "call_connector_tool"
#: Why a figure that *matches* a connector result is still not verified: the
#: owner's rule is that only a catalog connector marked ``trusted_data`` is
#: evidence, and every other one is somebody's own text.
UNTRUSTED_CONNECTOR = "untrusted_connector"


class FigureStatus(str, Enum):
    GROUNDED = "grounded"
    STALE = "stale"
    UNVERIFIED = "unverified"


class SourceKind(str, Enum):
    #: Rows a data tool returned: market bars, statement lines, calculations.
    STRUCTURED = "structured"
    PAGE = "page"
    SNIPPET = "snippet"
    #: A connector result whose catalog entry is not marked ``trusted_data``.
    #: Recorded and cited, never verifying.
    CONNECTOR = "connector"


#: Which kind of source wins when a figure appears in several. Structured tool
#: data first, then a page the model opened, then a snippet it only glimpsed,
#: and an untrusted connector last, so any source that can verify a figure does.
_KIND_RANK = {
    SourceKind.STRUCTURED: 0,
    SourceKind.PAGE: 1,
    SourceKind.SNIPPET: 2,
    SourceKind.CONNECTOR: 3,
}

#: The units a figure may carry, as a sentence here writes them. Longest first,
#: so ``tỷ đồng`` is read whole rather than as ``tỷ`` followed by a word.
_UNIT = re.compile(
    r"^[ \u00a0]*(%|per cent|percent|phần trăm|nghìn tỷ đồng|ngàn tỷ đồng|nghìn tỷ|ngàn tỷ|tỷ đồng|tỉ đồng|"
    r"triệu đồng|nghìn đồng|ngàn đồng|đồng/cp|đ/cp|đồng|đ|vnđ|vnd|dong|usd|tỷ|tỉ|triệu|tr|nghìn|"
    r"ngàn|trillion|billion|million|thousand|bn|mn|k|cp|cổ phiếu|shares|điểm|points|lần|times|x)(?![\w])",
    re.IGNORECASE,
)

_RANGE_END = re.compile(r"^[  ]*[-–][  ]*[-+−]?\d[\d.,]*")

#: What each magnitude word multiplies by, read off the word as written rather
#: than folded: folding makes ``ngân`` (bank) and ``ngàn`` (thousand) one word.
_SCALE = {
    "nghìn tỷ đồng": Decimal(10) ** 12,
    "ngàn tỷ đồng": Decimal(10) ** 12,
    "nghìn tỷ": Decimal(10) ** 12,
    "ngàn tỷ": Decimal(10) ** 12,
    "trillion": Decimal(10) ** 12,
    "tỷ đồng": Decimal(10) ** 9,
    "tỉ đồng": Decimal(10) ** 9,
    "tỷ": Decimal(10) ** 9,
    "tỉ": Decimal(10) ** 9,
    "billion": Decimal(10) ** 9,
    "bn": Decimal(10) ** 9,
    "triệu đồng": Decimal(10) ** 6,
    "triệu": Decimal(10) ** 6,
    "tr": Decimal(10) ** 6,
    "million": Decimal(10) ** 6,
    "mn": Decimal(10) ** 6,
    "nghìn đồng": Decimal(10) ** 3,
    "ngàn đồng": Decimal(10) ** 3,
    "nghìn": Decimal(10) ** 3,
    "ngàn": Decimal(10) ** 3,
    "thousand": Decimal(10) ** 3,
    "k": Decimal(10) ** 3,
}

#: Units that make a small number a financial figure. ``lần`` is absent: "gấp
#: 2–3 lần" is a speculation about the future, not a figure a source prints.
_FINANCIAL_UNITS = frozenset(
    {
        "%", "per cent", "percent", "phần trăm", "nghìn tỷ đồng", "ngàn tỷ đồng", "nghìn tỷ", "ngàn tỷ",
        "tỷ đồng", "tỉ đồng", "triệu đồng", "nghìn đồng", "ngàn đồng", "đồng/cp",
        "đ/cp", "đồng", "đ", "vnđ", "vnd", "dong", "usd", "tỷ", "tỉ", "triệu", "tr", "nghìn",
        "ngàn", "k", "cp", "cổ phiếu", "shares", "điểm", "points", "x",
    }
)

#: Dates and clock times, blanked before numbers are read so ``26/09/2026`` is a
#: date and not three figures. Same length out as in, so every offset still
#: points at the answer the reader sees.
_DATE_MASK = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:T[0-9:.+\-Z]+)?"  # ISO date or instant
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"  # 26/09/2026
    r"|\b\d{1,2}/\d{4}\b"  # 09/2026
    r"|\b\d{1,2}/\d{1,2}\b"  # 26/09
    r"|\b\d{1,2}:\d{2}\b"  # 14:30
    r"|(?i:\b(?:q|quý)\s*[1-4]\b)"  # Q3, quý 3
)
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_VN_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

#: Words that put a figure at "now". "Gần nhất" alone is not one of them:
#: "đỉnh gần nhất 79.000 đồng (11/09)" is the most recent peak, a dated past
#: figure, and only "phiên gần nhất" means the latest session. English mirrors
#: sit beside them, folded the same way: fold() is a no-op on plain ASCII.
_CURRENT = re.compile(
    r"\b(hien tai|hom nay|hien nay|luc nay|phien nay|dang o muc|"
    r"phien (?:gan nhat|moi nhat)|gia (?:gan nhat|moi nhat)|"
    r"current(?:ly)?|now|today|latest session|latest price)\b"
)
_YESTERDAY = re.compile(r"\bhom qua\b")
#: Words that let a line mean an earlier session without dating it: a peak, a
#: range, a level. Without one, a market figure that only an older row prints
#: is a coincidence in a three-month window, not that session's figure.
_EARLIER_WORDS = re.compile(
    r"\b(cao nhat|thap nhat|dinh|day|dao dong|trung binh|tu|truoc|so voi|tuan|thang|quy|"
    r"lich su|ky luc|vung|khoang|ho tro|khang cu|nguong|muc tieu|tung|bien dong|dien bien)\b"
    r"|→|->"
)
#: A reported ratio said to be priced today. P/E and P/B in a statement are
#: priced at the quarter's end; at today's price they are a ``calculate`` result.
_PRICED_NOW = re.compile(
    r"\b(?:theo|tinh theo|dua tren|voi)\s+gia\s+(?:dong cua\s+)?(?:gan nhat|hien tai|hom nay|moi nhat)\b"
)
# "Bán ròng 1,72tr" is a feed's "mua ròng -1.723.800" read by its sign.
_DOWN_WORDS = re.compile(
    r"(giam|mat|lo|am|sut|di xuong|thap hon|ban rong|"
    r"down|fell|declined|decreased|dropped|lower by)\s*$"
)
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}


# -- values ----------------------------------------------------------------


@dataclass(frozen=True)
class _Value:
    """One number, as written and in base units, with what stands beside it."""

    written: Decimal
    base: Decimal
    quantum: Decimal
    unit: str | None
    percent: bool
    #: A down word stands before it in the source: "giảm 1,31%" is -1,31%.
    down: bool = False

    # Cached: :func:`_same` asks it of one figure against every candidate value.
    @cached_property
    def significant(self) -> int:
        return numbers.significant_digits(self.written)


def _value(occurrence: numbers.Occurrence, trailing: str, *, down: bool = False) -> _Value:
    unit_match = _UNIT.match(trailing)
    if unit_match is None:
        # The start of a range takes the unit written after its end: "9,1-9,3%".
        span = _RANGE_END.match(trailing)
        unit_match = _UNIT.match(trailing[span.end() :]) if span else None
    unit = unit_match.group(1).lower() if unit_match else None
    written = occurrence.written
    factor = _SCALE.get(unit or "", Decimal(1))
    base = written * factor
    exponent = written.as_tuple().exponent
    quantum = (Decimal(10) ** int(exponent)) * factor if isinstance(exponent, int) else Decimal(1)
    return _Value(
        written=written,
        base=base,
        quantum=quantum,
        unit=unit,
        percent=unit in ("%", "phần trăm"),
        down=down,
    )


def _mask(text: str) -> str:
    """The text with dates, times and URLs blanked, offsets preserved."""

    def blank(match: re.Match[str]) -> str:
        return " " * (match.end() - match.start())

    return _DATE_MASK.sub(blank, _URL.sub(blank, text))


# -- sources ---------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    text: str
    when: date | None
    values: tuple[_Value, ...]


#: How each structured source dates a figure beside it, and how long its latest
#: line may stand for "now". A session is stale after a week; a quarter's ratios
#: stand until the next quarter's are due (a quarter plus the filing window).
#: Keyed by the answer's own language — the label a reader sees is built from
#: this, at :func:`annotate` time, from a role a :class:`_Source` already carries.
_ROLE_PREFIX = {
    "vi": {
        "market": "phiên",
        "statement": "kỳ đến",
        "calculation": "tính từ số liệu đến",
        "events": "ngày",
        "news": "tin ngày",
    },
    "en": {
        "market": "session",
        "statement": "period to",
        "calculation": "calculated from data to",
        "events": "event dated",
        "news": "news dated",
    },
}
_ROLE_FRESH_DAYS = {
    "market": CURRENT_SESSION_DAYS,
    "statement": 150,
    "calculation": 150,
    "events": 150,
    "news": NEWS_FRESH_DAYS,
}


@dataclass
class _Source:
    kind: SourceKind
    evidence: EvidenceRef
    lines: tuple[_Line, ...]
    published: date | None = None
    #: Structured sources only: the latest date a line names.
    latest: date | None = None
    label: str = ""
    #: ``market``, ``statement``, ``calculation``, ``page`` or ``snippet``.
    role: str = "page"
    #: A calculation's inputs, and whether every one was found in another source.
    inputs: tuple[_Value, ...] = ()
    valid: bool = True
    #: The tickers a structured source is about. A figure in a sentence that
    #: names tickers may only rest on structured data about one of them.
    symbols: frozenset[str] = frozenset()


#: A currency written against its digits, as English pages do: "VND64.2 trillion".
_CURRENCY_GLUE = re.compile(r"(?i)\b(vnd|usd|us\$|\$)(?=\d)")


def _values_of(text: str) -> tuple[_Value, ...]:
    # Measured 2026-09-27 (NVL): every "VND…" figure on three English pages was
    # invisible, so the answer's correct "64,2 nghìn tỷ" read as invented.
    text = _CURRENCY_GLUE.sub(lambda m: m.group(1) + " ", text)
    masked = _mask(text)
    found = []
    for occurrence in numbers.occurrences(masked):
        before = numbers.fold(text[max(0, occurrence.start - 24) : occurrence.start])
        found.append(
            _value(
                occurrence,
                text[occurrence.end : occurrence.end + 40],
                down=bool(_DOWN_WORDS.search(before)),
            )
        )
    return tuple(found)


def _line_date(text: str) -> date | None:
    iso = _ISO_DATE.search(text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    vn = _VN_DATE.search(text)
    if vn:
        try:
            return date(int(vn.group(3)), int(vn.group(2)), int(vn.group(1)))
        except ValueError:
            return None
    return None


def _payload(call: TurnToolCall) -> Mapping[str, Any] | None:
    try:
        value = json.loads(call.result_text or "")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, Mapping) else None


def _aware(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _day(moment: datetime | None) -> date | None:
    return None if moment is None else moment.astimezone(ICT).date()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: Any, excerpt: str) -> str:
    """The provider's content hash when it is one, else the excerpt's own."""
    text = str(value or "")
    return text if _HEX64.match(text) else _sha(excerpt)


def _source_class(value: Any, default: SourceClass = SourceClass.UNKNOWN) -> SourceClass:
    try:
        return SourceClass(str(value))
    except ValueError:
        return default


def _web_ref(item: Mapping[str, Any], excerpt: str, *, snippet: bool) -> EvidenceRef | None:
    url = str(item.get("canonical_url") or item.get("url") or "").strip()
    if not url or not excerpt.strip():
        return None
    try:
        canonical: str | None = canonical_url(url)
    except ValueError:
        canonical = None
    publication = item.get("publication")
    publication = publication if isinstance(publication, Mapping) else {}
    published = _aware(publication.get("publishedAt"))

    def enum(kind: type[Enum], key: str) -> Any:
        try:
            return kind(str(publication.get(key) or "unknown"))
        except ValueError:
            return kind("unknown")

    try:
        return build_evidence_ref(
            kind=EvidenceKind.WEB_PAGE,
            source_class=_source_class(item.get("source_class")),
            title=str(item.get("title") or item.get("publisher") or url).strip() or url,
            source=canonical or url,
            canonical_url=canonical,
            publisher=str(item.get("publisher") or item.get("source") or "web").strip() or "web",
            excerpt=excerpt,
            content_sha256=_sha(excerpt) if snippet else _digest(item.get("content_sha256"), excerpt),
            observed_at=_aware(item.get("retrieved_at")),
            published_at=published,
            publication_method=enum(PublicationMethod, "publicationMethod"),
            publication_confidence=enum(PublicationConfidence, "publicationConfidence"),
            publication_precision=enum(TimePrecision, "publicationPrecision"),
            tos_risk=_tos(item.get("tos_risk")),
        )
    except ValueError:
        return None


def _tos(value: Any) -> TosRisk:
    try:
        return TosRisk(str(value or "unknown"))
    except ValueError:
        return TosRisk.UNKNOWN


def _structured(call: TurnToolCall, payload: Mapping[str, Any]) -> _Source | None:
    """A data tool's rows: each line of its excerpt dated by the date it names.

    Written for the market read and open to any tool that returns an
    ``excerpt`` in the same shape — dated lines with units beside their figures
    — which is how a statements adapter or a calculator joins the check without
    this module learning its name.
    """
    excerpt = str(payload.get("excerpt") or "").strip()
    if not excerpt:
        return None
    calculation = str(payload.get("evidence_kind") or "") == EvidenceKind.CALCULATION.value
    if calculation:
        # Only the result is offered for matching. The inputs are printed in the
        # excerpt too, and a figure that matched them here would be grounded by
        # the calculator instead of by the source the input came from.
        result = str(payload.get("result_text") or "")
        lines = (_Line(text=excerpt, when=None, values=_values_of(result)),)
        inputs = tuple(_input_value(item) for item in payload.get("inputs") or () if isinstance(item, Mapping))
        role = "calculation"
    else:
        lines = tuple(
            _Line(text=line, when=_line_date(line), values=_values_of(line))
            for line in excerpt.splitlines()
            if line.strip()
        )
        inputs = ()
        role = str(payload.get("evidence_role") or ("market" if payload.get("interval") else "statement"))
    dated = [line.when for line in lines if line.when is not None]
    retrieved = _aware(payload.get("retrieved_at"))
    actual = payload.get("actual") if isinstance(payload.get("actual"), Mapping) else {}
    published = _aware(actual.get("end")) or _aware(payload.get("as_of")) or retrieved
    try:
        kind = EvidenceKind(str(payload.get("evidence_kind") or EvidenceKind.STORE_FIGURE.value))
    except ValueError:
        kind = EvidenceKind.STORE_FIGURE
    symbol = str(payload.get("symbol") or "").strip()
    first, last = _day(_aware(actual.get("start"))), _day(_aware(actual.get("end")))
    span = (
        f"{first.strftime('%d/%m/%Y')}–{last.strftime('%d/%m/%Y')}"
        if first and last and first != last
        else (last.strftime("%d/%m/%Y") if last else "")
    )
    title = str(payload.get("title") or "").strip() or " · ".join(
        part
        for part in (symbol, str(payload.get("interval_label") or "").strip(), span)
        if part
    ) or call.name
    publisher = str(payload.get("publisher") or payload.get("source") or call.name).strip()
    content = str(payload.get("content_sha256") or "")
    try:
        evidence = build_evidence_ref(
            kind=kind,
            source_class=_source_class(payload.get("source_class"), SourceClass.STORE),
            title=title,
            source=f"{payload.get('source') or call.name}/{symbol or call.id}",
            publisher=publisher or call.name,
            excerpt=excerpt,
            content_sha256=_digest(content, excerpt),
            observed_at=retrieved,
            published_at=published,
            publication_method=PublicationMethod.PROVIDER,
            publication_confidence=PublicationConfidence.HIGH,
            publication_precision=TimePrecision.INSTANT,
            tos_risk=TosRisk.MEDIUM,
        )
    except ValueError:
        return None
    return _Source(
        kind=SourceKind.STRUCTURED,
        evidence=evidence,
        lines=lines,
        published=_day(published),
        latest=max(dated) if dated else None,
        label=f"{publisher} — {title}",
        role=role,
        inputs=inputs,
        symbols=(
            frozenset(_TICKER.findall(excerpt))
            if calculation
            else frozenset(
                str(item).upper() for item in (payload.get("symbols") or ([symbol] if symbol else ()))
            )
        ),
    )


_TICKER = re.compile(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{2,9}(?![A-Za-z0-9])")


def _input_value(item: Mapping[str, Any]) -> _Value:
    """One calculator input as a figure the answer might have written."""
    written = Decimal(str(item.get("value") or "0"))
    unit = str(item.get("unit") or "").strip().lower() or None
    factor = _SCALE.get(unit or "", Decimal(1))
    exponent = written.as_tuple().exponent
    return _Value(
        written=written,
        base=written * factor,
        quantum=(Decimal(10) ** int(exponent)) * factor if isinstance(exponent, int) else Decimal(1),
        unit=unit,
        percent=unit in ("%", "phần trăm"),
    )


def _resolve_calculations(items: Sequence[_Source]) -> None:
    """Admit a calculation only when every input is printed in another source.

    Its date is its most recent input's: "P/B 2,30" from today's close over last
    quarter's book value describes today, and "tăng 52,7% từ đầu năm" describes
    the session it ends on.
    """
    others = [item for item in items if item.role != "calculation"]
    for source in items:
        if source.role != "calculation":
            continue
        dates: list[date] = []
        for value in source.inputs:
            probe = _Figure(text="", start=0, end=0, value=value, line="", before="")
            found = [
                line
                for other in others
                for line in other.lines
                if any(_same(probe, candidate) for candidate in line.values)
            ]
            if not found:
                source.valid = False
                break
            dated = [line.when for line in found if line.when is not None]
            if dated:
                dates.append(max(dated))
        if source.valid and dates:
            when = max(dates)
            source.lines = tuple(
                _Line(text=line.text, when=when, values=line.values) for line in source.lines
            )
            source.latest = when


def _web(item: Mapping[str, Any], excerpt: str, *, snippet: bool) -> _Source | None:
    evidence = _web_ref(item, excerpt, snippet=snippet)
    if evidence is None:
        return None
    published = _day(evidence.published_at)
    return _Source(
        kind=SourceKind.SNIPPET if snippet else SourceKind.PAGE,
        evidence=evidence,
        # One line for the whole page: a page's date is its publication, not a
        # date some sentence inside it happens to mention.
        lines=(_Line(text=excerpt, when=published, values=_values_of(excerpt)),),
        published=published,
        label=f"{evidence.publisher} — {evidence.title}",
        role="snippet" if snippet else "page",
    )


def _connector(call: TurnToolCall, payload: Mapping[str, Any]) -> _Source | None:
    """One connector result, as evidence when trusted and as a record otherwise.

    The envelope (``connector``, ``tool``, ``trusted_data``, ``retrieved_at``,
    ``content``) is written by the host's handler around the server's text, so
    the server cannot set ``trusted_data`` itself: its words are inside
    ``content``, never beside it.
    """
    if payload.get("is_error"):
        return None
    content = str(payload.get("content") or "").strip()
    if not content:
        return None
    trusted = payload.get("trusted_data") is True
    connector = str(payload.get("connector") or "connector")
    name = str(payload.get("connector_name") or connector)
    tool = str(payload.get("tool") or call.name)
    retrieved = _aware(payload.get("retrieved_at"))
    lines = tuple(
        _Line(text=line, when=_line_date(line), values=_values_of(line))
        for line in content.splitlines()
        if line.strip()
    )
    try:
        evidence = build_evidence_ref(
            kind=EvidenceKind.STORE_FIGURE if trusted else EvidenceKind.DOCUMENT_SECTION,
            source_class=SourceClass.STORE if trusted else SourceClass.UNKNOWN,
            title=f"{name} · {tool}",
            source=f"connector:{connector}/{tool}",
            publisher=name,
            excerpt=content[:2000],
            content_sha256=_digest(None, content),
            observed_at=retrieved,
            publication_method=PublicationMethod.PROVIDER,
            publication_confidence=PublicationConfidence.HIGH if trusted else PublicationConfidence.UNKNOWN,
            tos_risk=TosRisk.MEDIUM,
        )
    except ValueError:
        return None
    dated = [line.when for line in lines if line.when is not None]
    return _Source(
        kind=SourceKind.STRUCTURED if trusted else SourceKind.CONNECTOR,
        evidence=evidence,
        lines=lines,
        published=_day(retrieved),
        latest=max(dated) if dated else None,
        label=f"{name} — {tool}",
        role="connector",
    )


def _is_connector(call: TurnToolCall, payload: Mapping[str, Any]) -> bool:
    return (
        (call.name.startswith(CONNECTOR_PREFIX) or call.name == CONNECTOR_CALL_TOOL)
        and "connector" in payload
        and "content" in payload
    )


@dataclass(frozen=True)
class Sources:
    """What this Turn read, as the figure check reads it."""

    items: tuple[_Source, ...]
    exempt: tuple[_Value, ...]
    #: Dates the reader wrote, or that come back from their own memory.
    exempt_dates: _Dates = field(default_factory=lambda: _Dates(frozenset(), frozenset()))

    @property
    def latest_session(self) -> date | None:
        dates = [item.latest for item in self.items if item.role == "market" and item.latest is not None]
        return max(dates) if dates else None

    @property
    def evidence(self) -> tuple[EvidenceRef, ...]:
        return tuple(item.evidence for item in self.items)

    @cached_property
    def _by_magnitude(self) -> tuple[list[Decimal], list[tuple[int, int]]]:
        """Every line's values by absolute base value, sorted, with where each sits."""
        entries = sorted(
            (abs(value.base), at, index)
            for at, item in enumerate(self.items)
            for index, line in enumerate(item.lines)
            for value in line.values
        )
        return [entry[0] for entry in entries], [(entry[1], entry[2]) for entry in entries]

    @cached_property
    def _by_written(self) -> dict[Decimal, set[tuple[int, int]]]:
        found: dict[Decimal, set[tuple[int, int]]] = {}
        for at, item in enumerate(self.items):
            for index, line in enumerate(item.lines):
                for value in line.values:
                    found.setdefault(value.written, set()).add((at, index))
        return found

    def lines_near(self, wanted: _Value) -> list[tuple[_Source, _Line]]:
        """The lines that could hold ``wanted``, in reading order.

        A superset of the lines where :func:`_same` can hold: every match it
        accepts is within half a quantum of the figure's magnitude, whatever the
        sign, or prints the figure's digits as written. The window here is a
        whole quantum each side, so no rounding of the bounds can lose one.
        Reading order matters because the first of equally ranked sources wins.
        """
        keys, where = self._by_magnitude
        size = abs(wanted.base)
        found = set(
            where[bisect_left(keys, size - wanted.quantum) : bisect_right(keys, size + wanted.quantum)]
        )
        found |= self._by_written.get(wanted.written, set())
        return [(self.items[at], self.items[at].lines[index]) for at, index in sorted(found)]


def collect_sources(calls: Sequence[TurnToolCall], *, user_text: str = "") -> Sources:
    """Every source a figure could rest on, from the calls that returned one."""
    items: list[_Source] = []
    seen: set[str] = set()
    exempt: list[_Value] = list(_values_of(user_text or ""))
    exempt_text: list[str] = [user_text or ""]

    def add(source: _Source | None) -> None:
        if source is not None and source.evidence.evidence_id not in seen:
            seen.add(source.evidence.evidence_id)
            items.append(source)

    for call in calls:
        if call.status is not ToolCallStatus.OK:
            continue
        if call.name in EXEMPT_TOOLS:
            exempt.extend(_values_of(call.result_text or ""))
            exempt_text.append(call.result_text or "")
            continue
        payload = _payload(call)
        if payload is None:
            continue
        if _is_connector(call, payload):
            add(_connector(call, payload))
        elif call.name == PAGE_TOOL:
            add(_web(payload, str(payload.get("content") or "").strip(), snippet=False))
        elif call.name == SEARCH_TOOL:
            for item in payload.get("results") or ():
                if isinstance(item, Mapping):
                    add(_web(item, str(item.get("snippet") or "").strip(), snippet=True))
        elif isinstance(payload.get("parts"), list):
            # One call, several sources: a result that joins two publishers or
            # two kinds of date (a session and a quarter) declares each part,
            # and each is cited and dated on its own terms.
            for part in payload["parts"]:
                if isinstance(part, Mapping):
                    # The whole result's hash is not a part's: without its own
                    # digest every part would share one evidence id.
                    add(_structured(call, {**payload, "content_sha256": None, **part}))
        else:
            add(_structured(call, payload))
    _resolve_calculations(items)
    return Sources(
        items=tuple(items), exempt=tuple(exempt), exempt_dates=_dates_in("\n".join(exempt_text))
    )


# -- dates in the prose ------------------------------------------------------

#: How sources spell a date: 10/07/2026, 2026-07-10, 10-07-2026, "ngày 10 tháng 7
#: năm 2026". A page that omits the year ("ngày 10/7") still names the day.
_SOURCE_DMY = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_SOURCE_WORDS = re.compile(r"(?i)\b(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s*(?:năm|,)\s*(\d{4}))?")
_SOURCE_DM = re.compile(r"(?<![\d/.-])(\d{1,2})/(\d{1,2})(?![\d/])")
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH_WORD = (
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"(?:uary|ruary|ch|il|e|y|ust|t|tember|ober|ember)?\b\.?"
)
#: English pages: "September 30, 2025", "Sept. 30", "30 September 2025".
_SOURCE_EN_MDY = re.compile(
    rf"(?i)\b{_MONTH_WORD}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?"
)
_SOURCE_EN_DMY = re.compile(rf"(?i)\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MONTH_WORD}(?:\s+(\d{{4}}))?")


@dataclass(frozen=True)
class _Dates:
    """The full dates a text names, and the day/months it names without a year."""

    full: frozenset[date]
    day_month: frozenset[tuple[int, int]]

    def names(self, when: date) -> bool:
        return when in self.full or (when.day, when.month) in self.day_month


def _dates_in(text: str) -> _Dates:
    full: set[date] = set()
    day_month: set[tuple[int, int]] = set()

    def keep(day: str, month: str, year: str | None) -> None:
        try:
            if year:
                full.add(date(int(year), int(month), int(day)))
            elif 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                day_month.add((int(day), int(month)))
        except ValueError:
            pass

    folded = unicodedata.normalize("NFC", text)
    for match in _ISO_DATE.finditer(folded):
        keep(match.group(3), match.group(2), match.group(1))
    for match in _SOURCE_DMY.finditer(folded):
        keep(match.group(1), match.group(2), match.group(3))
    for match in _SOURCE_WORDS.finditer(folded):
        keep(match.group(1), match.group(2), match.group(3))
    for match in _SOURCE_EN_MDY.finditer(folded):
        keep(match.group(2), str(_MONTHS.index(match.group(1).lower()) + 1), match.group(3))
    for match in _SOURCE_EN_DMY.finditer(folded):
        keep(match.group(1), str(_MONTHS.index(match.group(2).lower()) + 1), match.group(3))
    for match in _SOURCE_DM.finditer(folded):
        keep(match.group(1), match.group(2), None)
    return _Dates(frozenset(full), frozenset(day_month))


def _source_dates(sources: Sources) -> _Dates:
    full: set[date] = set()
    day_month: set[tuple[int, int]] = set()
    for item in sources.items:
        found = _dates_in(f"{item.evidence.title}\n{item.evidence.excerpt}")
        full |= found.full | {when for when in (item.published, item.latest) if when}
        day_month |= found.day_month
    return _Dates(frozenset(full), frozenset(day_month))


def _check_dates(
    answer: str, sources: Sources, today: date, checked_until: int
) -> list[FigureCheck]:
    """Every full date the answer writes that nothing this Turn read names.

    Only ``dd/mm/yyyy``: a month or a bare year is too loose to hold a source to,
    and a wrong day on an appointment or a record date is the error readers act
    on. Grounded dates are not listed — they need no label and carry no figure.
    """
    named = _source_dates(sources)
    checks: list[FigureCheck] = []
    for match in _VN_DATE.finditer(_URL.sub(lambda m: " " * len(m.group(0)), answer)):
        if match.start() >= checked_until:
            break
        try:
            when = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            continue
        if when == today or named.names(when) or sources.exempt_dates.names(when):
            continue
        line_start = answer.rfind("\n", 0, match.start()) + 1
        line_end = answer.find("\n", match.end())
        checks.append(
            FigureCheck(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                value=Decimal(when.toordinal()),
                unit="date",
                status=FigureStatus.UNVERIFIED,
                line=answer[line_start : line_end if line_end != -1 else len(answer)],
                reason="date_not_in_sources",
            )
        )
    return checks


#: The Vietnamese weekday words, and the English names an answer or a source
#: may write instead ("Saturday" beside "thứ Bảy").
_WEEKDAY_WORD = (
    r"thứ\s*(?:hai|ba|tư|năm|sáu|bảy|[2-7])|chủ\s*nhật|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
)
_WEEKDAY_NUMBER = {"hai": 0, "2": 0, "ba": 1, "3": 1, "tư": 2, "4": 2, "năm": 3, "5": 3,
                   "sáu": 4, "6": 4, "bảy": 5, "7": 5}
_WEEKDAY_EN_NUMBER = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_WEEKDAY_NAME = ("thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật")
#: The reason code always names the weekday in Vietnamese — :func:`repair_note`
#: is what a reader (or the model rewriting a draft) actually sees, and it
#: translates this name to the answer's own language from there.
_WEEKDAY_NAME_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
#: "27/09/2026 là thứ Bảy", "27/09/2026 (Chủ nhật)", "thứ Bảy, 26/09/2026", "thứ 7 ngày 26/9/2026",
#: and the same shapes in English: "27/09/2026 is Saturday", "Friday, 25/09/2026".
_DATE_THEN_WEEKDAY = re.compile(
    rf"\b(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\b[\s*_)]*(?:là|is|,|\(|-|–)?[\s*_(]*(?:ngày\s+)?({_WEEKDAY_WORD})",
    re.IGNORECASE,
)
_WEEKDAY_THEN_DATE = re.compile(
    rf"({_WEEKDAY_WORD})[\s*_]*[,(\-–]?\s*(?:ngày\s+)?(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\b",
    re.IGNORECASE,
)


def _weekday_of(word: str) -> int:
    folded = re.sub(r"\s+", " ", word.lower()).strip()
    if folded in _WEEKDAY_EN_NUMBER:
        return _WEEKDAY_EN_NUMBER[folded]
    if folded.startswith("chủ"):
        return 6
    return _WEEKDAY_NUMBER[folded.split(" ", 1)[1] if " " in folded else folded[3:]]


def _check_weekdays(answer: str, checked_until: int) -> list[FigureCheck]:
    """A weekday written beside a full date that the calendar says it is not.

    Measured 2026-09-27 on kiro-glm-5: "Hôm nay 27/09/2026 là thứ Bảy" (a
    Sunday), twice in one round. The calendar is the host's to know.
    """
    checks: list[FigureCheck] = []
    found = [
        (m, m.group(4), m.group(1), m.group(2), m.group(3), m.start(4), m.end(4))
        for m in _DATE_THEN_WEEKDAY.finditer(answer)
    ] + [
        (m, m.group(1), m.group(2), m.group(3), m.group(4), m.start(1), m.end(1))
        for m in _WEEKDAY_THEN_DATE.finditer(answer)
    ]
    seen: set[int] = set()
    for match, word, day, month, year, start, end in sorted(found, key=lambda item: item[5]):
        if start >= checked_until or start in seen:
            continue
        seen.add(start)
        try:
            when = date(int(year), int(month), int(day))
        except ValueError:
            continue
        if _weekday_of(word) == when.weekday():
            continue
        line_start = answer.rfind("\n", 0, start) + 1
        line_end = answer.find("\n", end)
        checks.append(
            FigureCheck(
                text=answer[start:end],
                start=start,
                end=end,
                value=Decimal(when.toordinal()),
                unit="date",
                status=FigureStatus.UNVERIFIED,
                line=answer[line_start : line_end if line_end != -1 else len(answer)],
                reason=f"wrong_weekday:{_WEEKDAY_NAME[when.weekday()]}",
            )
        )
    return checks


#: A session described as happening today: "phiên hôm nay chưa đóng cửa",
#: "dữ liệu phiên 27/09/2026 chưa có do thị trường chưa đóng cửa", and the
#: same claim in English: "the market has not closed today".
_TODAY_SESSION = (
    r"(?:phiên|giao dịch|thị trường)[^.\n]{{0,40}}?(?:hôm nay|{today})"
    r"[^.\n]{{0,60}}?(?:chưa (?:có|đóng|kết thúc|hoàn tất)|đang (?:diễn ra|giao dịch))"
    r"|thị trường chưa đóng cửa"
    r"|(?:session|trading|market)[^.\n]{{0,40}}?(?:today|{today})"
    r"[^.\n]{{0,60}}?(?:has(?:n't| not) (?:closed|ended)|no closing data(?: yet)?|"
    r"is (?:currently )?(?:trading|ongoing|under way))"
    r"|market has(?:n't| not) closed"
)


def _check_session_today(answer: str, today: date, checked_until: int) -> list[FigureCheck]:
    """Today's session narrated on a day the market does not trade.

    The runtime tail says so (``market_today``) and the model still wrote
    "phiên hôm nay 27/09/2026 chưa có dữ liệu đóng cửa" on a Sunday — twice on
    2026-09-27. A reader takes that to mean a session is under way.
    """
    spelled = rf"0?{today.day}/0?{today.month}(?:/{today.year})?"
    pattern = re.compile(_TODAY_SESSION.format(today=spelled), re.IGNORECASE)
    checks: list[FigureCheck] = []
    for match in pattern.finditer(answer):
        if match.start() >= checked_until:
            break
        line_start = answer.rfind("\n", 0, match.start()) + 1
        line_end = answer.find("\n", match.end())
        checks.append(
            FigureCheck(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                value=Decimal(today.toordinal()),
                unit="date",
                status=FigureStatus.UNVERIFIED,
                line=answer[line_start : line_end if line_end != -1 else len(answer)],
                reason="no_session_today",
            )
        )
    return checks


# -- figures in the answer ---------------------------------------------------


@dataclass(frozen=True)
class FigureCheck:
    text: str
    start: int
    #: Past the figure's unit, which is where its annotation goes.
    end: int
    value: Decimal
    unit: str | None
    status: FigureStatus
    line: str
    evidence_id: str | None = None
    source_date: date | None = None
    reason: str | None = None
    kind: SourceKind | None = None
    #: The structured source's role ("market", "statement"…), which
    #: :func:`annotate` reads a "phiên"/"session" style prefix from in the
    #: answer's own language; ``None`` for a page or a snippet.
    date_prefix: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "value": str(self.value),
            "unit": self.unit,
            "status": self.status.value,
            "evidenceId": self.evidence_id,
            "sourceDate": self.source_date.isoformat() if self.source_date else None,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _Figure:
    text: str
    start: int
    end: int
    value: _Value
    line: str
    before: str


def _is_list_marker(answer: str, start: int, end: int) -> bool:
    line_start = answer.rfind("\n", 0, start) + 1
    before = answer[line_start:start]
    after = answer[end : end + 2]
    return not before.strip(" \t#*>-") and bool(re.match(r"[.)](\s|$)", after))


_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=\S)")


def _context(line: str, offset: int, header: str | None = None) -> str:
    """The part of a line a figure's time is read from.

    A table row whole — its first cell is usually the period ("Cuối 2025") and
    the figure sits in another cell — preceded by the header of the figure's
    own column, because a table as often names the period, or the ticker, only
    there: in "| Chỉ số | Q3/2025 | Q4/2025 |" the row "| Nợ/Vốn CSH | 0,93 |
    0,97 |" names no time at all, and on 2026-09-27 a Q4/2025 cell filled with
    Q2/2026's figure passed as grounded because of it. A line of prose, only
    the figure's own sentence: "đóng 76.500 đồng hôm qua. NPL 6,31%." puts
    "hôm qua" on the price, not on the ratio.
    """
    if line.lstrip().startswith("|"):
        if header is None:
            return line
        column = line[:offset].count("|") - 1
        cells = header.strip().strip("|").split("|")
        return f"{cells[column].strip()} {line}" if 0 < column < len(cells) else line
    start = 0
    for match in _SENTENCE_END.finditer(line):
        if match.start() >= offset:
            return line[start : match.start()]
        start = match.end()
    return line[start:]


def _table_header(answer: str, line_start: int) -> str | None:
    """The first row of the table the line at ``line_start`` sits in, when it is not that row."""
    header = None
    start = line_start
    while start > 0:
        previous = answer.rfind("\n", 0, start - 1) + 1
        if not answer[previous : start - 1].lstrip().startswith("|"):
            break
        header, start = answer[previous : start - 1], previous
    return header


def _header_unit(row_before: str, header: str) -> str | None:
    """The unit a cell's column header states in brackets: "| ROE (%) |" -> "%".

    Measured 2026-09-27: a DGC table wrote "(%)" once in the header and bare
    numbers in the cells, and all eight ROE and margin cells read as unitless
    and unverified against Vietcap's "13.75 %".
    """
    if not row_before.lstrip().startswith("|"):
        return None
    column = row_before.count("|") - 1
    cells = header.strip().strip("|").split("|")
    if not 0 <= column < len(cells):
        return None
    bracket = re.search(r"\(([^()]{1,20})\)", cells[column])
    if not bracket:
        return None
    unit = _UNIT.match(bracket.group(1).strip())
    return unit.group(1) if unit and unit.end() == len(bracket.group(1).strip()) else None


def _figures(answer: str) -> list[_Figure]:
    masked = _mask(answer)
    found: list[_Figure] = []
    for occurrence in numbers.occurrences(masked):
        start, end = occurrence.start, occurrence.end
        token = answer[start:end]
        trailing = answer[end : end + 40]
        value = _value(occurrence, trailing)
        line_start = answer.rfind("\n", 0, start) + 1
        header = _table_header(answer, line_start)
        if value.unit is None and header is not None:
            unit = _header_unit(answer[line_start:start], header)
            if unit:
                value = _value(occurrence, unit)
        if _is_list_marker(answer, start, end):
            continue
        if (
            token.isdigit()
            and 1900 <= int(token) <= 2100
            and value.unit not in _FINANCIAL_UNITS
        ):
            # A year. "năm 2025" names a period; the period rule reads it.
            continue
        financial = value.unit in _FINANCIAL_UNITS
        whole = value.written == value.written.to_integral_value()
        if whole and value.significant < 3 and abs(value.base) < 1000 and not financial:
            # "3 tháng", "5 năm", "top 10": counts, not figures a source prints.
            # A decimal is never a count — "| LPB | 0.86 |" is a P/B.
            continue
        unit_match = _UNIT.match(trailing)
        stop = end + (unit_match.end() if unit_match else 0)
        line_end = answer.find("\n", end)
        line = _context(
            answer[line_start : line_end if line_end != -1 else len(answer)],
            start - line_start,
            header,
        )
        found.append(
            _Figure(
                text=answer[start:stop],
                start=start,
                end=stop,
                value=value,
                line=line,
                before=numbers.fold(answer[max(line_start, start - 24) : start]),
            )
        )
    return found


def _same(figure: _Figure, value: _Value) -> bool:
    """Whether ``value`` in a source is ``figure``, as written or rounded."""
    wanted = figure.value
    if wanted.percent != value.percent:
        return False
    signs = [value.base]
    if value.base < 0 and wanted.base > 0 and _DOWN_WORDS.search(figure.before):
        # "giảm 0,65%" and a source's "-0,65%" are the same fact written twice.
        signs.append(-value.base)
    if value.base > 0 and wanted.base < 0 and value.down:
        # And the other way round: an answer's "-1,31%" and a page's "giảm 1,31%".
        signs.append(-value.base)
    small = wanted.significant < 3 and abs(wanted.base) < 1000
    for candidate in signs:
        if candidate == wanted.base:
            if small and not (value.unit or value.percent):
                continue
            return True
        if wanted.significant >= 3 or (
            wanted.significant >= 2 and (wanted.percent or wanted.unit in _SCALE)
        ):
            if abs(candidate - wanted.base) * 2 <= wanted.quantum:
                return True
    # The same digits in the source's own unit: a table printed "in tỷ đồng"
    # writes ``111.228`` where the answer writes ``111.228 tỷ``.
    if (
        wanted.significant >= 3
        and value.written == wanted.written
        and value.base == value.written
        and not wanted.percent
    ):
        return True
    return False


def _theirs(figure: _Figure, value: _Value) -> bool:
    """Whether the reader wrote this number themselves.

    By value alone: "P/B dưới 1,5?" in a question and "dưới 1,5 lần" in the
    answer are the reader's threshold repeated, whatever unit the answer adds.
    """
    return value.written == figure.value.written or value.base == figure.value.base


# -- time ------------------------------------------------------------------


@dataclass(frozen=True)
class _Period:
    start: date
    end: date


def _month_end(year: int, month: int) -> date:
    following = date(year + (month == 12), month % 12 + 1, 1)
    return following - timedelta(days=1)


def periods(line: str, today: date) -> tuple[tuple[_Period, ...], bool]:
    """The periods a line names, and whether it says it is about now."""
    # A date after "so với" (or its English mirror, "compared with"/"vs") is
    # what the figure is compared against, not when it was true: "232.000 đồng
    # (+0,87% so với phiên 24/09)" is the 25/09 close.
    text = re.sub(
        r"(?:so voi|compared (?:with|to)|vs\.?)\s*"
        r"(?:phien|ngay|cung ky|thang|quy|nam|q|session|day|period|month|quarter|year)?\s*[\d/\-]+",
        lambda m: " " * (m.end() - m.start()),
        numbers.fold(line),
    )
    found: list[_Period] = []

    def take(pattern: str, build) -> None:
        nonlocal text
        for match in list(re.finditer(pattern, text)):
            try:
                period = build(match)
            except ValueError:
                continue
            if period is not None:
                found.append(period)
        text = re.sub(pattern, lambda m: " " * (m.end() - m.start()), text)

    take(
        r"(\d{4})-(\d{2})-(\d{2})",
        lambda m: _Period(*(date(int(m[1]), int(m[2]), int(m[3])),) * 2),
    )
    take(
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        lambda m: _Period(*(date(int(m[3]), int(m[2]), int(m[1])),) * 2),
    )

    def quarter(m: re.Match[str]) -> _Period:
        number = m[1]
        index = int(number) if number.isdigit() else _ROMAN[number]
        year = int(m[2])
        return _Period(date(year, 3 * index - 2, 1), _month_end(year, 3 * index))

    take(r"\b(?:quy|q)\s*([1-4]|iv|iii|ii|i)\s*(?:/|-|nam)?\s*((?:19|20)\d\d)\b", quarter)

    def month(m: re.Match[str]) -> _Period | None:
        number, year = int(m[1]), int(m[2])
        if not 1 <= number <= 12:
            return None
        return _Period(date(year, number, 1), _month_end(year, number))

    take(r"\bthang\s*(\d{1,2})\s*(?:/|-|nam)?\s*((?:19|20)\d\d)\b", month)
    take(r"\b(\d{1,2})/((?:19|20)\d\d)\b", month)

    def day(m: re.Match[str]) -> _Period | None:
        number, month_number = int(m[1]), int(m[2])
        candidate = date(today.year, month_number, number)
        if candidate > today:
            candidate = date(today.year - 1, month_number, number)
        return _Period(candidate, candidate)

    take(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])", day)
    take(
        r"(?<!\d)((?:19|20)\d\d)(?!\d)",
        lambda m: _Period(date(int(m[1]), 1, 1), date(int(m[1]), 12, 31)),
    )
    if _YESTERDAY.search(text):
        found.append(_Period(today - timedelta(days=4), today - timedelta(days=1)))
    return tuple(found), bool(_CURRENT.search(text))


# -- the check -------------------------------------------------------------


@dataclass(frozen=True)
class GroundingReport:
    answer: str
    figures: tuple[FigureCheck, ...]
    sources: Sources
    today: date

    @property
    def unverified(self) -> tuple[FigureCheck, ...]:
        return tuple(item for item in self.figures if item.status is FigureStatus.UNVERIFIED)

    @property
    def repairable(self) -> tuple[FigureCheck, ...]:
        """Unverified figures a rewrite could fix.

        A figure found in an untrusted connector is not one of them: the
        reader's own tool said it, and the honest outcome is the label, not a
        rewrite that drops it.
        """
        return tuple(item for item in self.unverified if item.reason != UNTRUSTED_CONNECTOR)

    @property
    def stale(self) -> tuple[FigureCheck, ...]:
        return tuple(item for item in self.figures if item.status is FigureStatus.STALE)

    def to_payload(self) -> dict[str, Any]:
        return {
            "figures": [item.to_payload() for item in self.figures],
            "unverified": len(self.unverified),
            "stale": len(self.stale),
        }


def check_answer(
    answer: str,
    sources: Sources,
    *,
    today: date,
    skip_after: str | None = None,
    market_closed: bool = False,
) -> GroundingReport:
    """Decide every figure in ``answer`` against ``sources``.

    ``skip_after`` stops the check at a heading, for an answer that ends in its
    own list of sources: the dates and counts in a bibliography are not claims.
    ``market_closed`` says today has no session, from the same calendar the
    runtime tail states; an answer narrating one is then held to it.
    """
    checked_until = len(answer)
    if skip_after and skip_after in answer:
        checked_until = answer.index(skip_after)
    latest_session = sources.latest_session
    known = frozenset().union(
        *(item.symbols for item in sources.items if item.role in ("market", "statement"))
    )
    results: list[FigureCheck] = []
    for figure in _figures(answer):
        if figure.start >= checked_until:
            break
        if any(_theirs(figure, value) for value in sources.exempt):
            continue
        results.append(_decide(figure, sources, today, latest_session, known))
    results.extend(_check_dates(answer, sources, today, checked_until))
    results.extend(_check_weekdays(answer, checked_until))
    if market_closed:
        results.extend(_check_session_today(answer, today, checked_until))
    results.sort(key=lambda item: item.start)
    return GroundingReport(answer=answer, figures=tuple(results), sources=sources, today=today)


def _decide(
    figure: _Figure,
    sources: Sources,
    today: date,
    latest_session: date | None,
    known: frozenset[str],
) -> FigureCheck:
    """One figure's status; ``known`` is every ticker a market or statement read is about."""
    named, current = periods(figure.line, today)
    candidates: list[tuple[tuple[int, int, int], _Source, date | None, bool]] = []
    matched_somewhere = False
    invalid_calculation = False
    priced_now = False
    folded_line = numbers.fold(figure.line)
    named_symbols = frozenset(_TICKER.findall(figure.line)) & known
    for source, line in sources.lines_near(figure.value):
        if (
            named_symbols
            and source.kind is SourceKind.STRUCTURED
            and source.symbols
            and not (source.symbols & named_symbols)
        ):
            # "STB … 12,83%" cannot rest on TCB's statement line, however the
            # digits fall.
            continue
        if named_symbols and len(source.symbols) > 1:
            # A source about several tickers (a screen) answers for a ticker
            # only on that ticker's own line.
            own = frozenset(_TICKER.findall(line.text)) & source.symbols
            if own and not (own & named_symbols):
                continue
        if not any(_same(figure, value) for value in line.values):
            continue
        matched_somewhere = True
        if not source.valid:
            invalid_calculation = True
            continue
        when = line.when
        stale = False
        # A connector's text is dated like a page's, trusted or not: its
        # lines are prose a service wrote, not rows stamped with a session.
        if source.kind is SourceKind.STRUCTURED and source.role != "connector":
            if when is None:
                ok = not named and not current
            elif source.role == "statement" and _PRICED_NOW.search(folded_line):
                ok = False
                priced_now = True
            elif current:
                # "Hiện tại" is checked first and a date beside it does not
                # excuse it: "giá hiện tại 56.500 (26/09/2025)" names a real
                # session, a year before today, and calls it now — the exact
                # sentence a model working in its remembered year writes.
                newest = latest_session if source.role == "market" else source.latest
                ok = (
                    newest is not None
                    and when == newest
                    and (today - when).days <= _ROLE_FRESH_DAYS.get(source.role, CURRENT_SESSION_DAYS)
                )
            elif named and source.role == "news":
                # News is published after the period it reports on, like a page.
                ok = any(when >= period.start for period in named)
            elif named:
                ok = any(period.start <= when <= period.end for period in named)
            elif (
                source.role == "market"
                and source.latest is not None
                and when < source.latest
                and not _EARLIER_WORDS.search(folded_line)
            ):
                # Measured 2026-09-27: "Khối lượng: 1,99 triệu cổ phiếu" under
                # the 25/09 close matched only the 16/07 row. An undated
                # line reads as the latest session, and that one says otherwise.
                ok = False
            else:
                ok = True
                # A headline dates the news, not the figure; an old one is
                # an old source, the same as an old page.
                stale = source.role == "news" and (today - when).days > NEWS_FRESH_DAYS
        else:
            if named:
                # A period still ahead is a plan or a forecast, which a page
                # can only have published before it: "20% vào tháng 3/2027".
                ok = when is None or any(
                    when >= period.start or period.start > today for period in named
                )
            else:
                ok = True
                stale = when is not None and (today - when).days > WEB_FRESH_DAYS
        if not ok:
            continue
        rank = (
            _KIND_RANK[source.kind],
            1 if stale else 0,
            -(when.toordinal() if when else 0),
        )
        candidates.append((rank, source, when, stale))
    base = {
        "text": figure.text,
        "start": figure.start,
        "end": figure.end,
        "value": figure.value.base,
        "unit": figure.value.unit,
        "line": figure.line,
    }
    if not candidates:
        reason = (
            "calculation_inputs_unsupported"
            if invalid_calculation
            else "priced_at_period_end"
            if priced_now
            else ("wrong_period" if matched_somewhere else "not_in_sources")
        )
        return FigureCheck(**base, status=FigureStatus.UNVERIFIED, reason=reason)
    _, source, when, stale = min(candidates, key=lambda item: item[0])
    if source.kind is SourceKind.CONNECTOR:
        # Found, and not vouched for: labelled, and the evidence it rests on is
        # kept so the ledger can say where the number came from.
        return FigureCheck(
            **base,
            status=FigureStatus.UNVERIFIED,
            reason=UNTRUSTED_CONNECTOR,
            evidence_id=source.evidence.evidence_id,
            source_date=when,
            kind=source.kind,
        )
    if source.kind is not SourceKind.STRUCTURED and named and _contradicts_market(
        figure, named, sources
    ):
        # A page may print the same digits for another session; the feed says
        # what this session closed at, and it is the one that answers.
        return FigureCheck(**base, status=FigureStatus.UNVERIFIED, reason="conflicts_with_market_data")
    return FigureCheck(
        **base,
        status=FigureStatus.STALE if stale else FigureStatus.GROUNDED,
        evidence_id=source.evidence.evidence_id,
        source_date=when,
        kind=source.kind,
        date_prefix=source.role if source.role in _ROLE_PREFIX["vi"] else None,
    )


_PRICE_UNITS = frozenset({"đồng", "đ", "điểm", "dong", "points"})


#: How an answer spells an index, and the symbol a market read carries for it.
_INDEX_ALIASES = (
    (re.compile(r"(?i)\bvn[\s-]?index\b"), "VNINDEX"),
    (re.compile(r"(?i)\bhnx[\s-]?index\b"), "HNXINDEX"),
    (re.compile(r"(?i)\bupcom(?:[\s-]?index)?\b"), "UPCOMINDEX"),
    (re.compile(r"(?i)\bvn30[\s-]?index\b"), "VN30"),
    (re.compile(r"(?i)\bhnx30[\s-]?index\b"), "HNX30"),
)


def _line_symbols(line: str) -> frozenset[str]:
    """The tickers and indices a line names, indices under their market symbol."""
    for pattern, symbol in _INDEX_ALIASES:
        line = pattern.sub(symbol, line)
    return frozenset(_TICKER.findall(line))


def _contradicts_market(figure: _Figure, named: Sequence[_Period], sources: Sources) -> bool:
    """Whether market rows for the named session price it differently.

    Only for a figure that reads as a price or an index level — written in đồng
    or điểm, or unitless and within a factor of two of that session's prices. A
    page's "bán ròng 4.000 tỷ ngày 22/09" is not something a price feed could
    contradict, and is left to the page.
    """
    at = figure.line.find(figure.text)
    if figure.value.unit is None and at >= 0 and re.match(
        r"\s*[^\W\d_]", figure.line[at + len(figure.text) :]
    ):
        # A number with a noun after it counts something: "9.200 căn" is not a price.
        return False
    named_here = _line_symbols(figure.line)
    for source in sources.items:
        if source.kind is not SourceKind.STRUCTURED:
            continue
        if named_here and source.symbols and not (source.symbols & named_here):
            # VN30's close cannot be contradicted by VN-Index's row for the day.
            continue
        for line in source.lines:
            if line.when is None or not any(p.start <= line.when <= p.end for p in named):
                continue
            prices = [value for value in line.values if value.unit in _PRICE_UNITS and value.base]
            if not prices:
                continue
            wanted = figure.value
            price_like = wanted.unit in _PRICE_UNITS or (
                wanted.unit is None
                and any(Decimal("0.5") <= abs(wanted.base / value.base) <= 2 for value in prices)
            )
            if price_like and not any(_same(figure, value) for value in line.values):
                return True
    return False


# -- what the reader and the model are shown ---------------------------------

#: Every fixed label the host writes into or about an answer, keyed by the
#: language :func:`numbers.answer_language` reads off the answer itself — a
#: Vietnamese answer keeps exactly these Vietnamese words; an English one gets
#: their English mirror. The web client parses both sets back out of the prose.
UNVERIFIED_LABEL = {"vi": "chưa kiểm chứng", "en": "unverified"}
STALE_LABEL = {"vi": "nguồn cũ", "en": "stale source"}
UNDATED_LABEL = {"vi": "không rõ ngày", "en": "undated"}
SOURCES_HEADING = {"vi": "**Nguồn số liệu**", "en": "**Sources**"}
_PUBLISHED_WORD = {"vi": "đăng", "en": "published"}
_UNVERIFIED_NOTE = {
    "vi": "Số có nhãn [{label}] không có trong dữ liệu công cụ của lượt này, "
    "hoặc không khớp mốc thời gian câu đó nói tới.",
    "en": "Figures labelled [{label}] are not in this turn's tool data, or "
    "don't match the time the sentence refers to.",
}
#: The note beside a figure found only in a connector the reader attached: the
#: number is labelled, not repaired, and the note says whose data it is.
_CONNECTOR_NOTE = {
    "vi": "Số có nhãn [{label}] lấy từ kết nối {names}: dữ liệu do dịch vụ đó "
    "trả về, hệ thống chưa kiểm chứng.",
    "en": "Figures labelled [{label}] come from the connector {names}: data that "
    "service returned, which the system has not verified.",
}
_STALE_NOTE = {
    "vi": "Số có nhãn {label} lấy từ nguồn đã cũ: trang web đăng hơn {web_days} "
    "ngày, hoặc tin hơn {news_days} ngày trước hôm nay.",
    "en": "Figures labelled {label} come from an old source: a web page "
    "published more than {web_days} days ago, or a news item more than "
    "{news_days} days before today.",
}


def annotate(report: GroundingReport, *, cite: bool = True) -> str:
    """The answer with every checked figure labelled in place, and its sources.

    ``cite=False`` labels only what failed, for an answer that already cites its
    own sources (the deep lane's memo) and would otherwise be numbered twice.
    Every label is written in the answer's own language (owner decision,
    2026-09-27): the check runs once, and only the labels' words change.
    """
    answer = report.answer
    lang = numbers.answer_language(answer)
    by_id = {item.evidence.evidence_id: item for item in report.sources.items}
    # One number per address: a search snippet and the page it came from are
    # one source to a reader, whichever of the two a figure matched.
    key = {
        evidence_id: (
            item.evidence.canonical_url
            if item.kind is not SourceKind.STRUCTURED and item.evidence.canonical_url
            else evidence_id
        )
        for evidence_id, item in by_id.items()
    }
    order: list[str] = []
    shown: dict[str, str] = {}
    for figure in report.figures:
        if not cite or not figure.evidence_id or figure.status is FigureStatus.UNVERIFIED:
            continue
        address = key[figure.evidence_id]
        if address not in order:
            order.append(address)
        # The page wins over the snippet for the line in the source list.
        current = shown.get(address)
        if current is None or by_id[figure.evidence_id].kind is SourceKind.PAGE:
            shown[address] = figure.evidence_id

    pieces: list[str] = []
    cursor = 0
    for figure in sorted(report.figures, key=lambda item: item.start):
        label = _label(figure, order, key, cite=cite, lang=lang)
        if label is None:
            continue
        pieces.append(answer[cursor : figure.end])
        pieces.append(label)
        cursor = figure.end
    pieces.append(answer[cursor:])
    annotated = "".join(pieces)

    # Markdown blocks, not bare lines: consecutive lines are one paragraph to a
    # renderer, and the source list would read as a single run-on sentence.
    footer: list[str] = []
    if order:
        footer.append(
            SOURCES_HEADING[lang]
            + "\n\n"
            + "\n".join(
                f"- [{index}] {_source_line(by_id[shown[address]], lang)}"
                for index, address in enumerate(order, start=1)
            )
        )
    if report.repairable:
        footer.append(_UNVERIFIED_NOTE[lang].format(label=UNVERIFIED_LABEL[lang]))
    from_connectors = sorted(
        {
            by_id[figure.evidence_id].evidence.publisher or ""
            for figure in report.unverified
            if figure.reason == UNTRUSTED_CONNECTOR and figure.evidence_id in by_id
        }
    )
    if from_connectors:
        footer.append(
            _CONNECTOR_NOTE[lang].format(
                label=UNVERIFIED_LABEL[lang],
                names=", ".join(name for name in from_connectors if name),
            )
        )
    if report.stale and cite:
        footer.append(
            _STALE_NOTE[lang].format(
                label=STALE_LABEL[lang], web_days=WEB_FRESH_DAYS, news_days=NEWS_FRESH_DAYS
            )
        )
    if not footer:
        return annotated
    return f"{annotated.rstrip()}\n\n---\n\n" + "\n\n".join(footer)


def _label(
    figure: FigureCheck, order: list[str], key: Mapping[str, str], *, cite: bool, lang: str
) -> str | None:
    if figure.status is FigureStatus.UNVERIFIED:
        return f" [{UNVERIFIED_LABEL[lang]}]"
    address = key.get(figure.evidence_id or "")
    if not cite or address not in order:
        return None
    index = order.index(address) + 1
    if figure.source_date is None:
        when = UNDATED_LABEL[lang]
    elif figure.date_prefix:
        when = f"{_ROLE_PREFIX[lang][figure.date_prefix]} {figure.source_date.strftime('%d/%m/%Y')}"
    else:
        when = figure.source_date.strftime("%d/%m/%Y")
    stale = f" · {STALE_LABEL[lang]}" if figure.status is FigureStatus.STALE else ""
    return f" [{index} · {when}{stale}]"


def _source_line(source: _Source, lang: str) -> str:
    evidence = source.evidence
    if source.kind is SourceKind.STRUCTURED:
        return f"{evidence.publisher} — {evidence.title}"
    when = (
        f"{_PUBLISHED_WORD[lang]} {source.published.strftime('%d/%m/%Y')}"
        if source.published
        else UNDATED_LABEL[lang]
    )
    link = evidence.canonical_url or evidence.source
    return f"{evidence.publisher} — {evidence.title} — {when} — <{link}>"


#: The fixed "why" phrases :func:`repair_note` prints beside each unsupported
#: figure, and the fixed prose around them, one set per answer language. The
#: weekday reason is a template: the calendar's own name for the day is filled
#: in from :data:`_WEEKDAY_NAME` (Vietnamese) or its translation to English.
_REPAIR_WHY = {
    "vi": {
        "wrong_period": "có trong dữ liệu nhưng sai mốc thời gian câu đó nói tới",
        "date_not_in_sources": "ngày này không có trong dữ liệu công cụ của lượt này",
        "priced_at_period_end": "chỉ số báo cáo tính theo giá cuối kỳ, không phải giá "
        "gần nhất; theo giá hôm nay thì phải tính bằng calculate",
        "no_session_today": "hôm nay thị trường nghỉ, không có phiên giao dịch nào đang "
        "diễn ra; gắn số liệu với phiên gần nhất",
        "default": "không có trong dữ liệu công cụ của lượt này",
        "weekday": "sai thứ: ngày đó là {weekday}",
    },
    "en": {
        "wrong_period": "in the data, but for the wrong time the sentence refers to",
        "date_not_in_sources": "this date is not in this turn's tool data",
        "priced_at_period_end": "the ratio is priced at period end, not the latest price; "
        "at today's price it must be computed with calculate",
        "no_session_today": "the market is closed today, no session is under way; "
        "attach the figure to the latest session",
        "default": "not in this turn's tool data",
        "weekday": "wrong weekday: that date is {weekday}",
    },
}
_REPAIR_STRINGS = {
    "vi": {
        "in_sentence": "trong câu: «{line}»",
        "more_items": "- … và {more} số khác. Viết lại từ dữ liệu thay vì sửa từng số.",
        "latest_prices": "Dữ liệu giá mới nhất đã đọc:\n{facts}",
        "intro": "KIỂM SỐ LIỆU. Bản nháp dưới đây nêu những con số không được dữ liệu công cụ "
        "của lượt này chống lưng. Hôm nay là {today}.",
        "instruction": (
            "Viết lại TOÀN BỘ câu trả lời cho người dùng, bằng tiếng Việt — cùng ngôn ngữ với "
            "bản nháp dưới đây. Chỉ dùng con số có nguyên văn trong kết quả công cụ, kèm ngày "
            "của số liệu. Giá hiện tại lấy từ phiên gần nhất và ghi rõ ngày phiên. Số nào "
            "không có trong dữ liệu thì bỏ, hoặc nói rõ là chưa có dữ liệu — không ước lượng. "
            "Tỷ lệ, tăng trưởng hay chênh lệch tự tính thì bỏ, trừ khi đã có kết quả của công "
            "cụ calculate cho đúng phép tính đó. Ngày cụ thể (ngày/tháng/năm) cũng vậy: chỉ "
            "ghi ngày có trong kết quả công cụ, không thì chỉ nêu tháng. Không nhắc tới bản "
            "nháp hay việc kiểm số."
        ),
        "draft_label": "BẢN NHÁP",
    },
    "en": {
        "in_sentence": 'in the sentence: "{line}"',
        "more_items": "- … and {more} more figures. Rewrite from the data instead of fixing "
        "them one by one.",
        "latest_prices": "Latest price data read this turn:\n{facts}",
        "intro": "CHECK THE FIGURES. The draft below states figures this turn's tool data "
        "does not back. Today is {today}.",
        "instruction": (
            "Rewrite the ENTIRE answer for the user, in English — the same language as the "
            "draft below. Use only figures printed verbatim in a tool result, with the data's "
            "date. Take the current price from the latest session and name that session's "
            "date. Drop any figure not in the data, or say plainly that there is no data for "
            "it — do not estimate. Drop any self-computed ratio, growth rate or gap unless the "
            "calculate tool already returned that exact calculation. The same goes for an "
            "exact date (day/month/year): state only a date printed in a tool result, "
            "otherwise name only the month. Do not mention the draft or this check."
        ),
        "draft_label": "DRAFT",
    },
}


def repair_note(report: GroundingReport) -> str:
    """What the model is told when its draft states figures nothing backs.

    Written in the draft's own language (owner decision, 2026-09-27), and
    explicit about it — the instruction names the language rather than relying
    on the model to infer it from the prompt, which is what let an earlier,
    Vietnamese-only version of this note flip an English draft's rewrite back
    to Vietnamese.
    """
    lang = numbers.answer_language(report.answer)
    why_map = _REPAIR_WHY[lang]
    strings = _REPAIR_STRINGS[lang]
    items = []
    for figure in report.repairable[:MAX_REPAIR_ITEMS]:
        reason = figure.reason or ""
        if reason.startswith("wrong_weekday:"):
            vi_name = reason.split(":", 1)[1]
            weekday = vi_name if lang == "vi" else _WEEKDAY_NAME_EN[_WEEKDAY_NAME.index(vi_name)]
            why = why_map["weekday"].format(weekday=weekday)
        else:
            why = why_map.get(reason, why_map["default"])
        in_sentence = strings["in_sentence"].format(line=figure.line.strip()[:200])
        items.append(f'- "{figure.text}" ({why}) — {in_sentence}')
    more = len(report.repairable) - MAX_REPAIR_ITEMS
    if more > 0:
        items.append(strings["more_items"].format(more=more))
    latest = [
        line.text
        for source in report.sources.items
        if source.kind is SourceKind.STRUCTURED
        for line in source.lines
        if "PHIÊN GẦN NHẤT" in line.text
    ]
    facts = "\n".join(f"- {text}" for text in latest)
    return (
        strings["intro"].format(today=report.today.strftime("%d/%m/%Y")) + "\n"
        + "\n".join(items)
        + (f"\n{strings['latest_prices'].format(facts=facts)}" if facts else "")
        + f"\n\n{strings['instruction']}\n\n{strings['draft_label']}:\n<<<\n"
        + report.answer
        + "\n>>>"
    )


def to_ledger(report: GroundingReport, *, as_of: datetime) -> ClaimLedger:
    """The check as a claim ledger: one claim per figure, written for every Turn."""
    claims = []
    for index, figure in enumerate(report.figures, start=1):
        if figure.status is FigureStatus.UNVERIFIED:
            verdict = VerificationVerdict.UNSUPPORTED
        elif figure.status is FigureStatus.STALE:
            verdict = VerificationVerdict.TEMPORALLY_INVALID
        else:
            # One feed or one page per figure: the check finds where a number is
            # printed, not whether two publishers agree on it.
            verdict = VerificationVerdict.SINGLE_SOURCE
        text = figure.line.strip() or figure.text
        claims.append(
            VerifiedClaim(
                claim_id=f"g{index}",
                text=text[:1000],
                kind=ClaimKind.FACT,
                material=True,
                verdict=verdict,
                supporting_evidence_ids=(
                    (figure.evidence_id,)
                    if figure.evidence_id and verdict is not VerificationVerdict.UNSUPPORTED
                    else ()
                ),
                # Unsupported, and still traceable: the connector result the
                # figure was read from, which is not the same as backing it.
                invalidation_text=(
                    f"{UNTRUSTED_CONNECTOR}:{figure.evidence_id}"
                    if figure.reason == UNTRUSTED_CONNECTOR and figure.evidence_id
                    else None
                ),
                unit=figure.unit,
            )
        )
    cited = {claim.supporting_evidence_ids[0] for claim in claims if claim.supporting_evidence_ids}
    # Every connector result this Turn read is recorded, cited or not: which
    # connector, which tool and when it answered are in the evidence itself.
    cited |= {
        item.evidence.evidence_id
        for item in report.sources.items
        if item.role == "connector"
    }
    return ClaimLedger(
        version=LEDGER_VERSION,
        policy_version=POLICY_VERSION,
        as_of=as_of,
        evidence=tuple(item for item in report.sources.evidence if item.evidence_id in cited),
        claims=tuple(claims),
        gaps=tuple(
            f"{figure.text}: {figure.reason or 'unverified'}" for figure in report.unverified
        )[:40],
        assumptions=(),
        verifier_outcome=(
            VerifierOutcome.VERIFIED if not report.unverified else VerifierOutcome.INSUFFICIENT_EVIDENCE
        ),
    )


#: A figure label in the host's own format. The model copies it from earlier
#: answers in the Thread; a label it wrote vouches for nothing, so it is removed
#: before the check and only the host's labels reach the reader. Both
#: languages' spelling of "unverified" are stripped: a Thread can carry an
#: earlier Turn's answer in the other language.
_UNVERIFIED_ALTERNATION = "|".join(re.escape(value) for value in UNVERIFIED_LABEL.values())
_WRITTEN_LABEL = re.compile(rf" ?\[(?:\d{{1,3}} · [^\]\n]{{1,80}}|{_UNVERIFIED_ALTERNATION})\]")


def normalise(text: str) -> str:
    """The answer in composed form, without labels the model wrote itself."""
    return _WRITTEN_LABEL.sub("", unicodedata.normalize("NFC", text or ""))


__all__ = [
    "CURRENT_SESSION_DAYS",
    "FigureCheck",
    "FigureStatus",
    "GroundingReport",
    "LEDGER_VERSION",
    "Sources",
    "SourceKind",
    "WEB_FRESH_DAYS",
    "annotate",
    "check_answer",
    "collect_sources",
    "normalise",
    "periods",
    "repair_note",
    "to_ledger",
]
