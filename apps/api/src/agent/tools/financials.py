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
from .market_data import (
    FETCH_TIMEOUT_SECONDS,
    ICT,
    INTERNAL_PROFILE,
    MarketDataError,
    _import_vnstock,
    is_index,
)

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
        _import_vnstock()
        try:
            kbs = importlib.import_module("vnstock.explorer.kbs.financial")
            finance = kbs.Finance(
                symbol=symbol, period="quarter" if quarterly else "year"
            )
            raw = finance._fetch_financial_data(
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
        except Exception as exc:  # noqa: BLE001 - provider failures become a stable code
            raise MarketDataError(
                "provider_unavailable", "the statements provider did not answer this call"
            ) from exc
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
        provider: FinancialsProvider | None = None,
    ) -> None:
        self._settings_override = settings
        self._provider = provider or KbsFinancials()

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
                    "profitability (ROE, ROA, NIM, CIR), growth and liquidity. Use "
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
        statement = self._provider.ratios(symbol, quarterly=quarterly, periods=periods)
        if not statement.periods:
            raise MarketDataError("no_data", f"no unambiguous periods for {symbol}")
        now = (context.now or datetime.now(tz=ICT)).astimezone(ICT)
        latest = statement.periods[0]
        return {
            "symbol": symbol,
            "publisher": statement.publisher,
            "source": statement.source,
            "source_class": "store",
            "evidence_kind": "store_figure",
            "title": f"{symbol} · chỉ số tài chính · {latest.label}",
            "as_of": datetime.combine(latest.ended, datetime.min.time(), tzinfo=ICT).isoformat(),
            "retrieved_at": now.isoformat(),
            "content_sha256": statement.raw_sha256,
            "periods": [
                {
                    "label": period.label,
                    "ended": period.ended.isoformat(),
                    "published": period.published.isoformat() if period.published else None,
                    "figures": {figure.name: [figure.value, figure.unit] for figure in period.figures},
                }
                for period in statement.periods
            ],
            "dropped_periods": list(statement.dropped),
            "not_carried": list(statement.not_carried),
            "excerpt": render(statement),
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
    "Period",
    "Statement",
    "TOOL_NAME",
    "pair_periods",
    "register_financials_tools",
    "render",
]
