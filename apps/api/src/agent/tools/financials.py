"""Reported financial ratios for one listed company, through a replaceable adapter.

The seam is :class:`FinancialsProvider`. What the agent needs from a source of
financial statements is small and fixed — for each period, the figures, their
units, when the period ended and when it was published — and everything
source-specific stays behind that one method. The owner's rule (2026-09-26) is
that the free source serves development and tests only and that a paid provider
replaces it later without the rest of the harness changing; this protocol is
where that replacement plugs in.

**The development source is KB Securities' ratio feed, read through vnstock's
own HTTP client but not through its parser.** The parser sorts the period
headers by an ``ID`` that repeats (1, 2, 1, 2, …) while each row's ``Value{i}``
follows the headers' original order, so the labels it prints are shifted onto
the wrong quarters. Here ``Value{i}`` is paired with the *i*-th header as sent.

**A period the source lists twice is dropped, not guessed.** The raw feed has
carried three headers for one quarter with three different sets of values; no
rule recovers which one is the quarter, and a figure from the wrong one is worse
than a stated gap. The result names what was dropped.

**What the source does not carry is said out loud.** KB's feed has no
non-performing-loan ratio and no capital adequacy ratio for banks, so a question
about either is answered with that gap rather than with a figure found somewhere
else and presented as if this tool had returned it.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from src.core.config import Settings, get_settings

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    ToolPermission,
    object_schema,
    register,
)
from ..symbols import normalize_symbol
from . import vnstock_provider
from .market_data import FETCH_TIMEOUT_SECONDS, ICT, INTERNAL_PROFILE, is_index
from .vnstock_provider import MarketDataError, import_vnstock

logger = logging.getLogger(__name__)

TOOLSET = "market_data"
TOOL_NAME = "get_financial_ratios"
MAX_PERIODS = 8
DEFAULT_PERIODS = 4
MAX_RESULT_CHARS = 24_000
KBS_PAGE_SIZE = 8

#: Metrics a bank question asks for most, which this source does not publish.
#: Named so the tool can say so instead of the model filling the gap.
NOT_IN_KBS = ("tỷ lệ nợ xấu (NPL)", "hệ số an toàn vốn (CAR)")

_UNITS = {"vnđ": "đồng", "vnd": "đồng", "%": "%", "lần": "lần", "vòng": "vòng", "ngày": "ngày"}


@dataclass(frozen=True)
class Figure:
    name: str
    value: float
    unit: str


@dataclass(frozen=True)
class Period:
    """One reporting period as the source published it."""

    year: int
    quarter: int | None
    ended: date
    published: date | None
    figures: tuple[Figure, ...]

    @property
    def label(self) -> str:
        return f"Quý {self.quarter}/{self.year}" if self.quarter else f"Năm {self.year}"


@dataclass(frozen=True)
class Statement:
    symbol: str
    publisher: str
    source: str
    periods: tuple[Period, ...]
    dropped: tuple[str, ...] = ()
    not_carried: tuple[str, ...] = ()
    raw_sha256: str = ""


class FinancialsProvider(Protocol):
    """The adapter a statements source implements. One method, no pagination."""

    publisher: str
    source: str
    not_carried: tuple[str, ...]

    def ratios(self, symbol: str, *, quarterly: bool, periods: int) -> Statement: ...


def _period_end(year: int, quarter: int | None) -> date:
    if quarter is None:
        return date(year, 12, 31)
    month = quarter * 3
    following = date(year + (month == 12), month % 12 + 1, 1)
    return date.fromordinal(following.toordinal() - 1)


def _published(head: Mapping[str, Any]) -> date | None:
    for key in ("DatePubDepartment", "ReportDate"):
        raw = str(head.get(key) or "")[:10]
        try:
            return date.fromisoformat(raw)
        except ValueError:
            continue
    return None


def pair_periods(raw: Mapping[str, Any], *, quarterly: bool) -> tuple[list[Period], list[str]]:
    """KB's payload as periods: ``Value{i}`` with the *i*-th header, duplicates dropped."""
    heads = [head for head in raw.get("Head") or () if isinstance(head, Mapping)]
    keys: list[tuple[int, int | None]] = []
    for head in heads:
        term = str(head.get("TermCode") or "")
        quarter = int(term[1:]) if quarterly and term[:1] == "Q" and term[1:].isdigit() else None
        keys.append((int(head.get("YearPeriod") or 0), quarter))
    seen = Counter(keys)
    rows = [
        row
        for group in (raw.get("Content") or {}).values()
        if isinstance(group, Sequence)
        for row in group
        if isinstance(row, Mapping)
    ]
    periods: list[Period] = []
    dropped: list[str] = []
    for index, (head, key) in enumerate(zip(heads, keys), start=1):
        year, quarter = key
        label = f"Quý {quarter}/{year}" if quarter else f"Năm {year}"
        if seen[key] > 1:
            if label not in dropped:
                dropped.append(label)
            continue
        figures = []
        for row in rows:
            value = row.get(f"Value{index}")
            name = str(row.get("Name") or "").strip()
            if value is None or not name:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            unit = _UNITS.get(str(row.get("Unit") or "").strip().lower(), str(row.get("Unit") or "").strip())
            figures.append(Figure(name=name, value=number, unit=unit))
        periods.append(
            Period(
                year=year,
                quarter=quarter,
                ended=_period_end(year, quarter),
                published=_published(head),
                figures=tuple(figures),
            )
        )
    periods.sort(key=lambda item: item.ended, reverse=True)
    return periods, dropped


class KbsFinancials:
    """KB Securities' ratio feed. Development and tests only (owner, 2026-09-26)."""

    publisher = "KB Securities"
    source = "kbs"
    not_carried = NOT_IN_KBS

    def ratios(self, symbol: str, *, quarterly: bool, periods: int) -> Statement:
        import_vnstock()

        def read() -> Any:
            kbs = importlib.import_module("vnstock.explorer.kbs.financial")
            finance = kbs.Finance(symbol=symbol, period="quarter" if quarterly else "year")
            return finance._fetch_financial_data(
                report_type="CSTC",
                period_type=2 if quarterly else 1,
                page=1,
                # Always eight, whatever was asked. Measured on 2026-09-26: at
                # four the feed's values slide one period against its headers
                # (TCB's Q3/2025 figures arrived under Q2/2026), while six and
                # eight agree with each other and with the market close at each
                # quarter end. The page is trimmed to ``periods`` afterwards.
                page_size=KBS_PAGE_SIZE,
            )

        raw = vnstock_provider.call(read, symbol=symbol)
        if not isinstance(raw, Mapping):
            raise MarketDataError("no_data", f"the provider returned no statements for {symbol}")
        paired, dropped = pair_periods(raw, quarterly=quarterly)
        encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return Statement(
            symbol=symbol,
            publisher=self.publisher,
            source=self.source,
            periods=tuple(paired[:periods]),
            dropped=tuple(dropped),
            not_carried=self.not_carried,
            raw_sha256=hashlib.sha256(encoded).hexdigest(),
        )


#: Vietcap's ratio fields this tool reports, by the name a reader sees. Ratios
#: arrive as fractions and are printed as percentages; a field the source sets to
#: exactly 0 is treated as not published (CAR is 0 in every quarter the bank did
#: not disclose it, not a bank with no capital).
_VCI_FIELDS: tuple[tuple[str, str, str, float], ...] = (
    ("npl", "Tỷ lệ nợ xấu (NPL)", "%", 100.0),
    ("car", "Hệ số an toàn vốn (CAR)", "%", 100.0),
    ("loansLossReservesToNPLs", "Tỷ lệ bao phủ nợ xấu (dự phòng/nợ xấu)", "%", 100.0),
    ("roe", "ROE {span}", "%", 100.0),
    ("roa", "ROA {span}", "%", 100.0),
    ("netInterestMargin", "Biên lãi thuần (NIM) {span}", "%", 100.0),
    ("ldrLoanDepositRatio", "Tỷ lệ cho vay/huy động (LDR)", "%", 100.0),
    ("casaRatio", "Tỷ lệ CASA", "%", 100.0),
    ("pb", "P/B", "lần", 1.0),
    ("pe", "P/E", "lần", 1.0),
    ("grossMargin", "Biên lợi nhuận gộp {span}", "%", 100.0),
    ("afterTaxProfitMargin", "Biên lợi nhuận sau thuế {span}", "%", 100.0),
    ("debtToEquity", "Nợ/Vốn chủ sở hữu", "lần", 1.0),
    ("marketCap", "Vốn hóa", "tỷ đồng", 1e-9),
)


def pair_vci(records: Sequence[Mapping[str, Any]], *, quarterly: bool) -> tuple[list[Period], list[str]]:
    """Vietcap's ratio rows as periods; a period listed twice is dropped."""
    rows = []
    for record in records:
        try:
            year = int(record.get("year"))
            quarter = int(record.get("quarter"))
        except (TypeError, ValueError):
            continue
        kind = str(record.get("ratioType") or "")
        if quarterly and kind == "RATIO_TTM" and 1 <= quarter <= 4:
            rows.append(((year, quarter), record))
        elif not quarterly and (kind == "RATIO_YEAR" or quarter == 5):
            rows.append(((year, None), record))
    seen = Counter(key for key, _ in rows)
    span = "4 quý gần nhất" if quarterly else "cả năm"
    periods: list[Period] = []
    dropped: list[str] = []
    for (year, quarter), record in rows:
        label = f"Quý {quarter}/{year}" if quarter else f"Năm {year}"
        if seen[(year, quarter)] > 1:
            if label not in dropped:
                dropped.append(label)
            continue
        figures = []
        for field_name, name, unit, scale in _VCI_FIELDS:
            raw = record.get(field_name)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value != value or value == 0.0:  # NaN, or not published
                continue
            if field_name == "loansLossReservesToNPLs":
                # Reported with the reserve's balance-sheet sign; coverage is its size.
                value = abs(value)
            figures.append(Figure(name=name.format(span=span).strip(), value=round(value * scale, 2), unit=unit))
        periods.append(
            Period(year=year, quarter=quarter, ended=_period_end(year, quarter), published=None, figures=tuple(figures))
        )
    periods.sort(key=lambda item: item.ended, reverse=True)
    return periods, dropped


class VciFinancials:
    """Vietcap's ratio feed. Development and tests only (owner, 2026-09-26).

    The one free source found with a bank's NPL by quarter. Read raw through
    vnstock's client: its parser keeps the *first* four rows of a series sorted
    oldest-first, which is why it only ever returned 2018.
    """

    publisher = "Vietcap"
    source = "vci"
    not_carried: tuple[str, ...] = ()

    def ratios(self, symbol: str, *, quarterly: bool, periods: int) -> Statement:
        import_vnstock()

        def read() -> list[dict[str, Any]]:
            vci = importlib.import_module("vnstock.explorer.vci.financial")
            finance = vci.Finance(symbol=symbol, period="quarter" if quarterly else "year")
            frame = finance._get_report(
                "ratio", mode="raw", limit=10_000, period="quarter" if quarterly else "year"
            )
            return frame.to_dict(orient="records")

        # Two requests: Vietcap opens a session before it answers.
        records = vnstock_provider.call(read, symbol=symbol, weight=2)
        paired, dropped = pair_vci(records, quarterly=quarterly)
        encoded = json.dumps(records, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return Statement(
            symbol=symbol,
            publisher=self.publisher,
            source=self.source,
            periods=tuple(paired[:periods]),
            dropped=tuple(dropped),
            not_carried=self.not_carried,
            raw_sha256=hashlib.sha256(encoded).hexdigest(),
        )


#: Metrics a question often turns on, and the token that finds each in a
#: figure's name — so the result can say when no source had it for the latest
#: period, rather than leaving the model to fill the gap.
WATCHED_METRICS = {"tỷ lệ nợ xấu (NPL)": "NPL", "hệ số an toàn vốn (CAR)": "CAR"}


def missing_latest(statements: Sequence[Statement]) -> list[str]:
    """Watched metrics no source published for its latest period."""
    missing = []
    for label, token in WATCHED_METRICS.items():
        if not any(
            statement.periods and any(token in figure.name for figure in statement.periods[0].figures)
            for statement in statements
        ):
            missing.append(label)
    return missing


def _number(value: float, unit: str) -> str:
    """A figure the way a Vietnamese page prints it, with its unit."""
    whole = float(value).is_integer() and abs(value) >= 1000
    text = f"{value:,.0f}" if whole else f"{value:,.2f}"
    text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text}%" if unit == "%" else f"{text} {unit}".rstrip()


def render(statement: Statement) -> str:
    """One dated line per period: the figure check dates a figure by its line."""
    lines = [
        f"{statement.symbol} · chỉ số tài chính · nguồn {statement.publisher} · "
        "mỗi dòng bắt đầu bằng ngày kết thúc kỳ"
    ]
    for period in statement.periods:
        published = (
            f" (công bố {period.published.strftime('%d/%m/%Y')})" if period.published else ""
        )
        figures = " · ".join(
            f"{figure.name} {_number(figure.value, figure.unit)}" for figure in period.figures
        )
        lines.append(f"{period.ended.isoformat()}: {period.label}{published} · {figures}")
    if statement.dropped:
        lines.append(
            "Bỏ qua vì nguồn liệt kê trùng kỳ, không xác định được số liệu đúng: "
            + ", ".join(statement.dropped)
        )
    if statement.not_carried:
        lines.append("Nguồn này không cung cấp: " + ", ".join(statement.not_carried))
    return "\n".join(lines)


class FinancialsTools:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        providers: Sequence[FinancialsProvider] | None = None,
    ) -> None:
        self._settings_override = settings
        # Both free sources, each for what only it has: KB's quarterly ROE,
        # EPS and book value; Vietcap's asset quality. A paid provider replaces
        # the pair by implementing the same protocol.
        self._providers = tuple(providers) if providers else (KbsFinancials(), VciFinancials())

    def _settings(self) -> Settings:
        return self._settings_override or get_settings()

    def available(self) -> bool:
        settings = self._settings()
        return (
            settings.deployment_profile == INTERNAL_PROFILE and settings.market_data_enabled
        )

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name=TOOL_NAME,
                toolset=TOOLSET,
                description=(
                    "Read one listed Vietnamese company's reported financial ratios "
                    "by quarter or year: valuation (EPS, BVPS, P/E, P/B), "
                    "profitability (ROE, ROA, NIM, CIR), and for banks asset quality "
                    "(NPL, coverage, CAR when published), LDR and CASA. Use "
                    "it for any ratio before searching the web, and quote each "
                    "figure with its period. Each line starts with the period's end "
                    "date. The result says which metrics the source does not carry; "
                    "say those are missing rather than estimating them."
                ),
                schema=object_schema(
                    {
                        "symbol": {"type": "string", "minLength": 1},
                        "period": {
                            "type": "string",
                            "enum": ["quarter", "year"],
                            "description": "Quarterly (default) or annual ratios.",
                        },
                        "periods": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": MAX_PERIODS,
                            "description": f"How many recent periods, default {DEFAULT_PERIODS}.",
                        },
                    },
                    ("symbol",),
                ),
                handler=self.get_financial_ratios,
                display_name="Đọc chỉ số tài chính",
                summarise=_summarise,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.NETWORK,
                content_trust=ContentTrust.UNTRUSTED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                permission=ToolPermission.ALLOW,
                resource_arg="symbol",
                is_async=False,
                timeout_seconds=FETCH_TIMEOUT_SECONDS,
                contract_version="1",
                check_fn=self.available,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    def get_financial_ratios(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        try:
            symbol = normalize_symbol(str(arguments.get("symbol") or ""))
        except ValueError as exc:
            raise MarketDataError("invalid_request", str(exc)) from exc
        if is_index(symbol):
            raise MarketDataError("invalid_request", f"{symbol} is an index and has no statements")
        quarterly = str(arguments.get("period") or "quarter") != "year"
        wanted = arguments.get("periods")
        periods = max(1, min(MAX_PERIODS, int(wanted))) if wanted is not None else DEFAULT_PERIODS
        if not self.available():
            raise MarketDataError(
                "provider_unavailable", "financial statements are not enabled on this deployment"
            )
        statements: list[Statement] = []
        failed: list[str] = []
        for provider in self._providers:
            try:
                statement = provider.ratios(symbol, quarterly=quarterly, periods=periods)
            except MarketDataError:
                failed.append(provider.publisher)
                continue
            if statement.periods:
                statements.append(statement)
        if not statements:
            raise MarketDataError("no_data", f"no unambiguous periods for {symbol}")
        now = (context.now or datetime.now(tz=ICT)).astimezone(ICT)
        latest = max((statement.periods[0] for statement in statements), key=lambda p: p.ended)
        missing = missing_latest(statements)
        excerpt = "\n".join(
            render(Statement(**{**statement.__dict__, "not_carried": ()})) for statement in statements
        )
        if failed:
            excerpt += "\nKhông trả lời lượt này: " + ", ".join(failed)
        if missing:
            excerpt += "\nKỳ gần nhất chưa có trong nguồn nào: " + ", ".join(missing)
        digest = hashlib.sha256("".join(s.raw_sha256 for s in statements).encode()).hexdigest()
        return {
            "symbol": symbol,
            "publisher": "; ".join(statement.publisher for statement in statements),
            "source": "+".join(statement.source for statement in statements),
            "source_class": "store",
            "evidence_kind": "store_figure",
            "title": f"{symbol} · chỉ số tài chính · {latest.label}",
            "as_of": datetime.combine(latest.ended, datetime.min.time(), tzinfo=ICT).isoformat(),
            "retrieved_at": now.isoformat(),
            "content_sha256": digest,
            "statements": [
                {
                    "publisher": statement.publisher,
                    "periods": [
                        {
                            "label": period.label,
                            "ended": period.ended.isoformat(),
                            "published": period.published.isoformat() if period.published else None,
                            "figures": {f.name: [f.value, f.unit] for f in period.figures},
                        }
                        for period in statement.periods
                    ],
                    "dropped_periods": list(statement.dropped),
                }
                for statement in statements
            ],
            "unavailable_providers": failed,
            "not_carried": missing,
            "excerpt": excerpt,
        }


def _summarise(arguments: Mapping[str, Any]) -> str:
    symbol = str(arguments.get("symbol") or "?").strip().upper()
    period = "năm" if str(arguments.get("period") or "") == "year" else "quý"
    return f"Đọc chỉ số tài chính {symbol} · theo {period}"


def register_financials_tools(*, settings: Settings | None = None) -> tuple[ToolEntry, ...]:
    return tuple(register(entry) for entry in FinancialsTools(settings=settings).entries())


__all__ = [
    "FinancialsProvider",
    "FinancialsTools",
    "Figure",
    "KbsFinancials",
    "NOT_IN_KBS",
    "VciFinancials",
    "missing_latest",
    "pair_vci",
    "Period",
    "Statement",
    "TOOL_NAME",
    "pair_periods",
    "register_financials_tools",
    "render",
]
