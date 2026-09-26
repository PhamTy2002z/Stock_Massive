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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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


class FigureStatus(str, Enum):
    GROUNDED = "grounded"
    STALE = "stale"
    UNVERIFIED = "unverified"


class SourceKind(str, Enum):
    #: Rows a data tool returned: market bars, statement lines, calculations.
    STRUCTURED = "structured"
    PAGE = "page"
    SNIPPET = "snippet"


#: Which kind of source wins when a figure appears in several. Structured tool
#: data first, then a page the model opened, then a snippet it only glimpsed.
_KIND_RANK = {SourceKind.STRUCTURED: 0, SourceKind.PAGE: 1, SourceKind.SNIPPET: 2}

#: The units a figure may carry, as a sentence here writes them. Longest first,
#: so ``tỷ đồng`` is read whole rather than as ``tỷ`` followed by a word.
_UNIT = re.compile(
    r"^[ \u00a0]*(%|phần trăm|nghìn tỷ đồng|ngàn tỷ đồng|nghìn tỷ|ngàn tỷ|tỷ đồng|tỉ đồng|"
    r"triệu đồng|nghìn đồng|ngàn đồng|đồng/cp|đ/cp|đồng|đ|vnđ|vnd|usd|tỷ|tỉ|triệu|nghìn|"
    r"ngàn|trillion|billion|million|thousand|bn|mn|k|cp|cổ phiếu|điểm|lần|x)(?![\w])",
    re.IGNORECASE,
)

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
        "%", "phần trăm", "nghìn tỷ đồng", "ngàn tỷ đồng", "nghìn tỷ", "ngàn tỷ",
        "tỷ đồng", "tỉ đồng", "triệu đồng", "nghìn đồng", "ngàn đồng", "đồng/cp",
        "đ/cp", "đồng", "đ", "vnđ", "vnd", "usd", "tỷ", "tỉ", "triệu", "nghìn",
        "ngàn", "k", "cp", "cổ phiếu", "điểm", "x",
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

_CURRENT = re.compile(
    r"\b(hien tai|hom nay|hien nay|moi nhat|gan nhat|luc nay|phien nay|dang o muc)\b"
)
_YESTERDAY = re.compile(r"\bhom qua\b")
_DOWN_WORDS = re.compile(r"(giam|mat|lo|am|sut|di xuong|thap hon)\s*$")
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

    @property
    def significant(self) -> int:
        return numbers.significant_digits(self.written)


def _value(occurrence: numbers.Occurrence, trailing: str) -> _Value:
    unit_match = _UNIT.match(trailing)
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


@dataclass
class _Source:
    kind: SourceKind
    evidence: EvidenceRef
    lines: tuple[_Line, ...]
    published: date | None = None
    #: Market sources only: the latest session a row names.
    latest: date | None = None
    label: str = ""


def _values_of(text: str) -> tuple[_Value, ...]:
    masked = _mask(text)
    found = []
    for occurrence in numbers.occurrences(masked):
        found.append(_value(occurrence, text[occurrence.end : occurrence.end + 40]))
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
    lines = tuple(
        _Line(text=line, when=_line_date(line), values=_values_of(line))
        for line in excerpt.splitlines()
        if line.strip()
    )
    dated = [line.when for line in lines if line.when is not None]
    retrieved = _aware(payload.get("retrieved_at"))
    actual = payload.get("actual") if isinstance(payload.get("actual"), Mapping) else {}
    published = _aware(actual.get("end")) or _aware(payload.get("as_of")) or retrieved
    try:
        kind = EvidenceKind(str(payload.get("evidence_kind") or EvidenceKind.STORE_FIGURE.value))
    except ValueError:
        kind = EvidenceKind.STORE_FIGURE
    symbol = str(payload.get("symbol") or "").strip()
    title = str(payload.get("title") or "").strip() or " · ".join(
        part for part in (symbol, str(payload.get("interval_label") or "").strip()) if part
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
    )


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
    )


@dataclass(frozen=True)
class Sources:
    """What this Turn read, as the figure check reads it."""

    items: tuple[_Source, ...]
    exempt: tuple[_Value, ...]

    @property
    def latest_session(self) -> date | None:
        dates = [item.latest for item in self.items if item.latest is not None]
        return max(dates) if dates else None

    @property
    def evidence(self) -> tuple[EvidenceRef, ...]:
        return tuple(item.evidence for item in self.items)


def collect_sources(calls: Sequence[TurnToolCall], *, user_text: str = "") -> Sources:
    """Every source a figure could rest on, from the calls that returned one."""
    items: list[_Source] = []
    seen: set[str] = set()
    exempt: list[_Value] = list(_values_of(user_text or ""))

    def add(source: _Source | None) -> None:
        if source is not None and source.evidence.evidence_id not in seen:
            seen.add(source.evidence.evidence_id)
            items.append(source)

    for call in calls:
        if call.status is not ToolCallStatus.OK:
            continue
        if call.name in EXEMPT_TOOLS:
            exempt.extend(_values_of(call.result_text or ""))
            continue
        payload = _payload(call)
        if payload is None:
            continue
        if call.name == PAGE_TOOL:
            add(_web(payload, str(payload.get("content") or "").strip(), snippet=False))
        elif call.name == SEARCH_TOOL:
            for item in payload.get("results") or ():
                if isinstance(item, Mapping):
                    add(_web(item, str(item.get("snippet") or "").strip(), snippet=True))
        else:
            add(_structured(call, payload))
    return Sources(items=tuple(items), exempt=tuple(exempt))


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


def _context(line: str, offset: int) -> str:
    """The part of a line a figure's time is read from.

    A table row whole — its first cell is usually the period ("Cuối 2025") and
    the figure sits in another cell. A line of prose, only the figure's own
    sentence: "đóng 76.500 đồng hôm qua. NPL 6,31%." puts "hôm qua" on the
    price, not on the ratio.
    """
    if line.lstrip().startswith("|"):
        return line
    start = 0
    for match in _SENTENCE_END.finditer(line):
        if match.start() >= offset:
            return line[start : match.start()]
        start = match.end()
    return line[start:]


def _figures(answer: str) -> list[_Figure]:
    masked = _mask(answer)
    found: list[_Figure] = []
    for occurrence in numbers.occurrences(masked):
        start, end = occurrence.start, occurrence.end
        token = answer[start:end]
        trailing = answer[end : end + 40]
        value = _value(occurrence, trailing)
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
        if value.significant < 3 and abs(value.base) < 1000 and not financial:
            # "3 tháng", "5 năm", "top 10": counts, not figures a source prints.
            continue
        unit_match = _UNIT.match(trailing)
        stop = end + (unit_match.end() if unit_match else 0)
        line_start = answer.rfind("\n", 0, start) + 1
        line_end = answer.find("\n", end)
        line = _context(answer[line_start : line_end if line_end != -1 else len(answer)], start - line_start)
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
    small = wanted.significant < 3 and abs(wanted.base) < 1000
    for candidate in signs:
        if candidate == wanted.base:
            if small and not (value.unit or value.percent):
                continue
            return True
        if wanted.significant >= 3 or (wanted.percent and wanted.significant >= 2):
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
    text = numbers.fold(line)
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
) -> GroundingReport:
    """Decide every figure in ``answer`` against ``sources``.

    ``skip_after`` stops the check at a heading, for an answer that ends in its
    own list of sources: the dates and counts in a bibliography are not claims.
    """
    checked_until = len(answer)
    if skip_after and skip_after in answer:
        checked_until = answer.index(skip_after)
    latest_session = sources.latest_session
    results: list[FigureCheck] = []
    for figure in _figures(answer):
        if figure.start >= checked_until:
            break
        if any(_same(figure, value) for value in sources.exempt):
            continue
        results.append(_decide(figure, sources, today, latest_session))
    return GroundingReport(answer=answer, figures=tuple(results), sources=sources, today=today)


def _decide(
    figure: _Figure, sources: Sources, today: date, latest_session: date | None
) -> FigureCheck:
    named, current = periods(figure.line, today)
    candidates: list[tuple[tuple[int, int, int], _Source, date | None, bool]] = []
    matched_somewhere = False
    for source in sources.items:
        for line in source.lines:
            if not any(_same(figure, value) for value in line.values):
                continue
            matched_somewhere = True
            when = line.when
            stale = False
            if source.kind is SourceKind.STRUCTURED:
                if when is None:
                    ok = not named and not current
                elif named:
                    ok = any(period.start <= when <= period.end for period in named)
                elif current:
                    ok = (
                        latest_session is not None
                        and when == latest_session
                        and (today - when).days <= CURRENT_SESSION_DAYS
                    )
                else:
                    ok = True
            else:
                if named:
                    ok = when is None or any(when >= period.start for period in named)
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
        return FigureCheck(
            **base,
            status=FigureStatus.UNVERIFIED,
            reason="wrong_period" if matched_somewhere else "not_in_sources",
        )
    _, source, when, stale = min(candidates, key=lambda item: item[0])
    return FigureCheck(
        **base,
        status=FigureStatus.STALE if stale else FigureStatus.GROUNDED,
        evidence_id=source.evidence.evidence_id,
        source_date=when,
        kind=source.kind,
    )


# -- what the reader and the model are shown ---------------------------------

UNVERIFIED_LABEL = "chưa kiểm chứng"
STALE_LABEL = "nguồn cũ"
UNDATED_LABEL = "không rõ ngày"
SOURCES_HEADING = "**Nguồn số liệu**"


def annotate(report: GroundingReport, *, cite: bool = True) -> str:
    """The answer with every checked figure labelled in place, and its sources.

    ``cite=False`` labels only what failed, for an answer that already cites its
    own sources (the deep lane's memo) and would otherwise be numbered twice.
    """
    answer = report.answer
    by_id = {item.evidence.evidence_id: item for item in report.sources.items}
    order: list[str] = []
    for figure in report.figures:
        if cite and figure.evidence_id and figure.evidence_id not in order:
            order.append(figure.evidence_id)

    pieces: list[str] = []
    cursor = 0
    for figure in sorted(report.figures, key=lambda item: item.start):
        label = _label(figure, order, cite=cite)
        if label is None:
            continue
        pieces.append(answer[cursor : figure.end])
        pieces.append(label)
        cursor = figure.end
    pieces.append(answer[cursor:])
    annotated = "".join(pieces)

    footer: list[str] = []
    if order:
        footer.append(SOURCES_HEADING)
        for index, evidence_id in enumerate(order, start=1):
            source = by_id[evidence_id]
            footer.append(f"[{index}] {_source_line(source)}")
    if report.unverified:
        footer.append(
            f"Số có nhãn [{UNVERIFIED_LABEL}] không có trong dữ liệu công cụ của lượt "
            "này, hoặc không khớp mốc thời gian câu đó nói tới."
        )
    if report.stale and cite:
        footer.append(
            f"Số có nhãn [{STALE_LABEL}] lấy từ nguồn đăng hơn {WEB_FRESH_DAYS} ngày "
            "trước hôm nay."
        )
    if not footer:
        return annotated
    return f"{annotated.rstrip()}\n\n---\n" + "\n".join(footer)


def _label(figure: FigureCheck, order: list[str], *, cite: bool) -> str | None:
    if figure.status is FigureStatus.UNVERIFIED:
        return f" [{UNVERIFIED_LABEL}]"
    if not cite or figure.evidence_id not in order:
        return None
    index = order.index(figure.evidence_id) + 1
    if figure.source_date is None:
        when = UNDATED_LABEL
    elif figure.kind is SourceKind.STRUCTURED:
        when = f"phiên {figure.source_date.strftime('%d/%m/%Y')}"
    else:
        when = figure.source_date.strftime("%d/%m/%Y")
    stale = f" · {STALE_LABEL}" if figure.status is FigureStatus.STALE else ""
    return f" [{index} · {when}{stale}]"


def _source_line(source: _Source) -> str:
    evidence = source.evidence
    if source.kind is SourceKind.STRUCTURED:
        return f"{evidence.publisher} — {evidence.title}"
    when = (
        f"đăng {source.published.strftime('%d/%m/%Y')}"
        if source.published
        else UNDATED_LABEL
    )
    link = evidence.canonical_url or evidence.source
    return f"{evidence.publisher} — {evidence.title} — {when} — <{link}>"


def repair_note(report: GroundingReport) -> str:
    """What the model is told when its draft states figures nothing backs."""
    items = []
    for figure in report.unverified[:MAX_REPAIR_ITEMS]:
        why = (
            "có trong dữ liệu nhưng sai mốc thời gian câu đó nói tới"
            if figure.reason == "wrong_period"
            else "không có trong dữ liệu công cụ của lượt này"
        )
        items.append(f'- "{figure.text}" ({why}) — trong câu: «{figure.line.strip()[:200]}»')
    more = len(report.unverified) - MAX_REPAIR_ITEMS
    if more > 0:
        items.append(f"- … và {more} số khác. Viết lại từ dữ liệu thay vì sửa từng số.")
    latest = [
        line.text
        for source in report.sources.items
        if source.kind is SourceKind.STRUCTURED
        for line in source.lines
        if "PHIÊN GẦN NHẤT" in line.text
    ]
    facts = "\n".join(f"- {text}" for text in latest)
    return (
        "KIỂM SỐ LIỆU. Bản nháp dưới đây nêu những con số không được dữ liệu công cụ "
        f"của lượt này chống lưng. Hôm nay là {report.today.strftime('%d/%m/%Y')}.\n"
        + "\n".join(items)
        + (f"\nDữ liệu giá mới nhất đã đọc:\n{facts}" if facts else "")
        + "\n\nViết lại TOÀN BỘ câu trả lời cho người dùng. Chỉ dùng con số có nguyên "
        "văn trong kết quả công cụ, kèm ngày của số liệu. Giá hiện tại lấy từ phiên "
        "gần nhất và ghi rõ ngày phiên. Số nào không có trong dữ liệu thì bỏ, hoặc "
        "nói rõ là chưa có dữ liệu — không ước lượng, không tự tính tỷ lệ hay tăng "
        "trưởng. Không nhắc tới bản nháp hay việc kiểm số.\n\nBẢN NHÁP:\n<<<\n"
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
                unit=figure.unit,
            )
        )
    cited = {claim.supporting_evidence_ids[0] for claim in claims if claim.supporting_evidence_ids}
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


def normalise(text: str) -> str:
    """The answer in composed form, which is how the unit patterns are written."""
    return unicodedata.normalize("NFC", text or "")


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
