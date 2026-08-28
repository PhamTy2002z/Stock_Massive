"""Which companies' quarterly profit jumped while their price has not followed.

The question a reader asks is *mã nào lợi nhuận tăng mạnh mà giá chưa phản
ánh?*, and it is a screen rather than a query: the answer is a distribution over
the whole market with a handful of names standing out of it. Four decisions make
the difference between a screen and a recommendation engine, and each of them is
load-bearing here.

**"Giá chưa tăng" is measured against the market, not against zero.** A quarter
in which every symbol fell 8% and this one fell 6% is not a symbol whose price
has not moved. So the price axis is the twenty-session return minus VN-Index's
return over the same span, and the raw return travels beside it in the ranking
so a reader can see both.

**The composite is named after what it measures.** ``dislocation_rank`` is the
growth percentile times the percentile of the *negated* relative return, taken
over the symbols this run could actually measure. It says "far apart on these
two axes within this sample" and nothing else — no target, no horizon, no view
on what a reader should do with it. The earlier name for a number of this shape
was "opportunity score", and a reader cannot help but read that as advice.

**Every symbol the screen dropped is counted and named.** A screener that
answers "12 mã" out of a market of 1.522 without saying what happened to the
other 1.510 is a screener nobody can check. Each symbol is counted at the first
gate it fails, in the fixed order of :data:`GATES`, so the exclusions plus the
survivors add up to the universe exactly.

**The liquidity floor is a gate, not a factor.** ``adtv ≥ 3 tỷ đồng/phiên``
removes what cannot be traded before any percentile is taken; as a multiplier it
would be a multiplication by one for everything that survived it, and the
percentiles would be ranks against a population including symbols nobody can
buy.

## What the data forced, measured 2026-08-27

**There is no traded-value column.** ``bar_daily`` carries ``open, high, low,
close, volume`` and nothing else, so the liquidity floor is the median of
``close × volume`` across the window. That is an approximation of traded value —
the real figure is matched price times matched quantity, bar by bar — and the
provenance says so rather than letting the number pass as turnover.

**There is no publication date.** The provider returns statements by period and
never says when a filing was released, so a window anchored to the release date
cannot be built from this store. The reaction window is therefore the last
:data:`REACTION_SESSIONS` closed sessions, which for a quarter's screen is
roughly the month after the filing season — and the provenance states the
limitation instead of implying a date nobody has.

**Price basis does not disturb the price axis.** Every ``bar_daily`` row is
``adjusted_at_source``; a return and a return-minus-index are ratios, so they
survive adjustment except on the one session an ex-date falls in the window. The
guard against a window that mixes bases is still here, and it is a guard: no row
in the store has ever carried a second basis.

**Survivorship is the current roster.** ``listing_roster`` is refreshed to now,
so a company delisted last year is absent from a screen of last year's quarter.
Reconstructing the roster as it stood at a past period is out of scope for this
version, and the provenance records it.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.stocks.financial import reads as financial_reads, templates
from src.stocks.financial.templates import Concept, ConceptValue
from src.stocks.listing_roster import ListingRosterStore
from src.stocks.models import BarDaily, FinancialStatementLine
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.cross_sectional import percentile_of
from src.stocks.signals.fields import PERCENTILE_ABSOLUTE_FLOOR
from src.stocks.signals.issues import SignalIssue

from .contracts import (
    SignalDeskBlock,
    SignalDeskSpec,
    Frame,
    Provenance,
    StudyContext,
    StudyDefinition,
    StudyRefused,
    StudyResult,
)
from .reads_daily import (
    INDEX_SYMBOL,
    SERIES_EQUITY,
    SERIES_INDEX,
    SESSION_SETTLED_AT,
)
from .registry import register

NAME = "earnings_dislocation_screener"
VERSION = 1

#: The price reaction window, in closed sessions. A return over ``n`` sessions is
#: measured between ``n + 1`` closes, which is what :data:`WINDOW_CLOSES` is.
#: Twenty because that is about the month a quarter's filings land in, and fixed
#: rather than parameterised: two runs of this screen must not disagree about
#: what "giá chưa theo" was measured over.
REACTION_SESSIONS = 20
WINDOW_CLOSES = REACTION_SESSIONS + 1

#: How far back the market-wide price read reaches, in calendar days. Twenty-one
#: sessions is about thirty calendar days; the extra fortnight covers a Tết week
#: and the ordinary holidays without loading a quarter of the market's history
#: for a window of one month.
CALENDAR_LOOKBACK_DAYS = 45

#: The liquidity floor, in dong of median daily traded value. Three billion is
#: roughly what a retail-sized position can leave without moving the price, and
#: below it a "dislocation" is a symbol nobody traded rather than a symbol the
#: market has not repriced.
LIQUIDITY_FLOOR_VND = 3_000_000_000.0

DEFAULT_MIN_PROFIT_GROWTH_PCT = 20.0
DEFAULT_MAX_PRICE_CHANGE_PCT = 5.0

DEFAULT_TOP_N = 10
TOP_N_FLOOR = 1
TOP_N_CEILING = 20

#: How many ranked rows reach the model. The Signal Desk draws ``top_n``; the headline
#: is budgeted at roughly three hundred tokens, and ten rows of four figures is
#: already most of it.
HEADLINE_TOP = 10

#: How the default period is chosen. The newest quarter is always half-filed —
#: the market reports over weeks — so the default is the newest quarter holding
#: at least this share of what the store's fullest recent quarter holds. Measured
#: against the store rather than against the market: a scan still walking the
#: roster would otherwise make every quarter look empty.
PERIOD_COVERAGE_SHARE = 0.8
PERIODS_CONSIDERED = 8

#: Below this share of the universe carrying a filing for the period, the strip
#: says the screen is thinner than a screen of the market. The plan's own line:
#: a screener run over a store with sparse coverage reports a fact about the
#: store, and a reader has to be told which one they are looking at.
HEALTHY_FILING_COVERAGE = 0.85

PERIOD_PATTERN = re.compile(r"^\d{4}-Q[1-4]$")

Universe = Literal["market", "declared"]

#: The gates, in the order every symbol meets them. A symbol is counted at the
#: first one it fails and never twice, which is what makes the exclusions plus
#: the survivors equal to the universe.
GATE_NO_FILING = "no_filing"
GATE_CONCEPT_UNKNOWN = "concept_unknown"
GATE_NO_PRIOR_FILING = "no_prior_filing"
GATE_PRIOR_CONCEPT_UNKNOWN = "prior_concept_unknown"
GATE_NON_POSITIVE_PROFIT = "non_positive_profit"
GATE_NON_POSITIVE_PRIOR_PROFIT = "non_positive_prior_profit"
GATE_INSUFFICIENT_PRICE_HISTORY = "insufficient_price_history"
GATE_PRICE_WINDOW_UNUSABLE = "price_window_unusable"
GATE_THIN_LIQUIDITY = "thin_liquidity"
GATE_BELOW_GROWTH_THRESHOLD = "below_growth_threshold"
GATE_ABOVE_PRICE_CHANGE = "above_price_change"

#: The gates a symbol has to pass to be *measurable*: after these it has both
#: coordinates and can be plotted, whatever the thresholds then say about it.
MEASUREMENT_GATES = (
    GATE_NO_FILING,
    GATE_CONCEPT_UNKNOWN,
    GATE_NO_PRIOR_FILING,
    GATE_PRIOR_CONCEPT_UNKNOWN,
    GATE_NON_POSITIVE_PROFIT,
    GATE_NON_POSITIVE_PRIOR_PROFIT,
    GATE_INSUFFICIENT_PRICE_HISTORY,
    GATE_PRICE_WINDOW_UNUSABLE,
    GATE_THIN_LIQUIDITY,
)

#: The two gates that are the reader's question rather than the store's limits.
THRESHOLD_GATES = (GATE_BELOW_GROWTH_THRESHOLD, GATE_ABOVE_PRICE_CHANGE)

GATES = MEASUREMENT_GATES + THRESHOLD_GATES

#: What each gate removed, in the words a reader sees under the table. Every one
#: of them describes a state of the data or of the measurement — none of them
#: describes what the symbol is worth.
GATE_LABELS: Mapping[str, str] = {
    GATE_NO_FILING: "Chưa có báo cáo kỳ này trong store",
    GATE_CONCEPT_UNKNOWN: "Báo cáo không có dòng lợi nhuận sau thuế",
    GATE_NO_PRIOR_FILING: "Chưa có báo cáo cùng kỳ năm trước",
    GATE_PRIOR_CONCEPT_UNKNOWN: "Báo cáo cùng kỳ không có dòng lợi nhuận",
    GATE_NON_POSITIVE_PROFIT: "Lợi nhuận kỳ này không dương",
    GATE_NON_POSITIVE_PRIOR_PROFIT: "Lợi nhuận cùng kỳ không dương",
    GATE_INSUFFICIENT_PRICE_HISTORY: "Không đủ phiên giá đã đóng trong cửa sổ",
    GATE_PRICE_WINDOW_UNUSABLE: "Cửa sổ giá không so được",
    GATE_THIN_LIQUIDITY: "Thanh khoản dưới sàn",
    GATE_BELOW_GROWTH_THRESHOLD: "Tăng trưởng lợi nhuận dưới ngưỡng",
    GATE_ABOVE_PRICE_CHANGE: "Giá đã tăng quá ngưỡng so với thị trường",
}

#: The four regions of the scatter, named for what is true in them. Descriptive
#: on purpose: a quadrant labelled "rất hấp dẫn" is a verdict drawn on a chart,
#: and the whole point of drawing two axes is that the reader compares them.
QUADRANT_HIGH_GROWTH_LOW_PRICE = "Tăng trưởng cao, giá chưa theo"
QUADRANT_HIGH_GROWTH_HIGH_PRICE = "Tăng trưởng cao, giá đã theo"
QUADRANT_LOW_GROWTH_LOW_PRICE = "Tăng trưởng thấp, giá giảm so với thị trường"
QUADRANT_LOW_GROWTH_HIGH_PRICE = "Tăng trưởng thấp, giá tăng so với thị trường"

#: What the numbers are and are not, in the field a reader and the model both
#: see. This is the only carrier a Signal Desk has for a methodological limit, and
#: every clause here is a limit this Study cannot design away.
METHOD_NOTES = (
    "thanh khoản là trung vị giá đóng cửa × khối lượng trên cửa sổ, xấp xỉ cho "
    "giá trị giao dịch vì nguồn không trả cột này",
    f"cửa sổ phản ứng giá là {REACTION_SESSIONS} phiên gần nhất chứ không tính "
    "từ ngày công bố — nguồn không trả ngày công bố của từng báo cáo",
    "dislocation_rank = phân vị tăng trưởng × phân vị lợi suất tương đối đảo "
    "dấu, tính trên các mã đo được sau sàn thanh khoản "
    f"{LIQUIDITY_FLOOR_VND / 1e9:.0f} tỷ đồng một phiên",
    "giá là adjusted_at_source; lợi suất là tỷ số nên không đổi theo điều chỉnh, "
    "trừ đúng phiên giao dịch không hưởng quyền",
    "universe lấy từ roster niêm yết hiện hành, không dựng lại danh sách của "
    "quá khứ",
)


class EarningsDislocationParams(BaseModel):
    """What the model fills in.

    ``period`` is optional because the answer to "which quarter has the market
    reported" is a fact about the store, and a model guessing at it would ask
    for a quarter half the market has not filed. ``top_n`` clamps rather than
    refuses, like every other Study's window: a model asking for fifty names has
    asked a sensible question with an unusable number.
    """

    period: str | None = Field(
        default=None,
        description=(
            "Kỳ báo cáo dạng 2026-Q2. Bỏ trống để dùng quý gần nhất mà store đã "
            "có đủ báo cáo."
        ),
    )
    min_profit_growth_pct: float = Field(
        default=DEFAULT_MIN_PROFIT_GROWTH_PCT,
        description=(
            "Sàn tăng trưởng lợi nhuận sau thuế so với cùng kỳ năm trước, tính "
            "theo phần trăm"
        ),
    )
    max_price_change_pct: float = Field(
        default=DEFAULT_MAX_PRICE_CHANGE_PCT,
        description=(
            f"Trần lợi suất {REACTION_SESSIONS} phiên so với VN-Index, tính theo "
            "phần trăm; mã vượt trần là mã giá đã theo"
        ),
    )
    top_n: int = Field(
        default=DEFAULT_TOP_N,
        description=(
            f"Số mã trong bảng xếp hạng, {TOP_N_FLOOR}–{TOP_N_CEILING}; ngoài "
            "khoảng sẽ được kẹp về biên"
        ),
    )
    universe: Universe = Field(
        default="market",
        description=(
            "market = toàn bộ mã đang niêm yết, declared = 30 mã Universe khai báo"
        ),
    )

    @field_validator("period")
    @classmethod
    def _period_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().upper()
        if not PERIOD_PATTERN.match(text):
            raise ValueError("period must look like 2026-Q2")
        return text

    @field_validator("top_n")
    @classmethod
    def _clamp(cls, value: int) -> int:
        return max(TOP_N_FLOOR, min(TOP_N_CEILING, value))


@dataclass(frozen=True)
class _Close:
    """One closed session of one symbol, in the four columns a screen needs.

    Narrower than :class:`reads_daily.DailyBar` because the read behind it is
    market-wide: a month of the whole market is some forty thousand rows, and
    the open, the high and the low are three columns no gate here reads.
    """

    trading_day: date
    close: float
    volume: int
    price_basis: str


@dataclass(frozen=True)
class _IndexWindow:
    """VN-Index over the same calendar span, and the close at or before a day.

    "At or before" rather than "on": a symbol trades on a subset of the market's
    sessions, and its window's first session is a session the index also has.
    The walk backwards is the guard for the day that stops being true.
    """

    days: tuple[date, ...]
    closes: tuple[float, ...]

    def close_at(self, day: date) -> float | None:
        position = bisect_right(self.days, day) - 1
        if position < 0:
            return None
        return self.closes[position]


@dataclass(frozen=True)
class _Candidate:
    """One symbol that carries both coordinates, with every input it needed."""

    symbol: str
    net_profit_vnd: float
    prior_net_profit_vnd: float
    growth_pct: float
    return_pct: float
    index_return_pct: float
    rel_return_pct: float
    adtv_vnd: float
    window_end: date


@dataclass(frozen=True)
class _Ranked:
    """A candidate with its standing inside the measured sample.

    Both percentiles and the product travel together because the product is the
    only one of the three that is not a measurement, and a reader shown a
    composite without its components has been shown a verdict.
    """

    candidate: _Candidate
    growth_percentile: float
    rel_return_percentile: float
    dislocation_rank: float


def compute(context: StudyContext) -> StudyResult:
    """Screen the universe for the period, and rank what survived.

    Store-only by construction: three reads — the filings for two quarters, the
    market's last month of closes, the index's — and arithmetic. No provider
    call, which is what lets the same question re-run to the same numbers and
    what keeps a market-wide screen inside one tool round.
    """
    params = context.params
    assert isinstance(params, EarningsDislocationParams)
    session = context.session

    period = params.period or _default_period(session)
    if period is None:
        raise StudyRefused(
            SignalIssue.FUNDAMENTAL_NOT_STORED,
            "the store holds no quarterly statement line, so there is no period "
            "to screen",
        )
    prior = _prior_period(period)

    symbols = _universe(session, params.universe, context.universe)
    if not symbols:
        raise StudyRefused(
            SignalIssue.RANKING_UNAVAILABLE,
            f"the {params.universe} universe is empty, so there is nothing to "
            "screen",
        )

    current = financial_reads.concepts_for_period(session, period, symbols=symbols)
    previous = financial_reads.concepts_for_period(session, prior, symbols=symbols)
    windows = _price_windows(session, symbols, context.as_of)
    index = _index_window(session, context.as_of)

    counts = dict.fromkeys(GATES, 0)
    candidates: list[_Candidate] = []
    for symbol in symbols:
        measured = _measure(
            symbol,
            current.get(symbol),
            previous.get(symbol),
            windows.get(symbol, ()),
            index,
        )
        if isinstance(measured, str):
            counts[measured] += 1
        else:
            candidates.append(measured)

    if len(candidates) < PERCENTILE_ABSOLUTE_FLOOR:
        # The floor is the absolute one the Signal Field pack uses
        # (``signals/fields.py``) and not ``min_sample_for``: that function
        # takes a share of the sample asked for, which assumes every member is
        # expected to answer. Here exclusion is the screen's own product — most
        # of a market of 1.522 legitimately fails a liquidity floor — so a share
        # of the roster would refuse every honest run.
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_CROSS_SECTION,
            f"{len(candidates)} of {len(symbols)} symbols carry a {period} "
            f"filing, its year-ago comparison and a {REACTION_SESSIONS}-session "
            f"price window above the liquidity floor; "
            f"{PERCENTILE_ABSOLUTE_FLOOR} are needed before a percentile over "
            "them means anything",
        )

    ranked = _rank(candidates)
    matched, threshold_counts = _apply_thresholds(
        ranked, params.min_profit_growth_pct, params.max_price_change_pct
    )
    counts.update(threshold_counts)
    top = matched[: params.top_n]

    # Coverage counts the symbols whose profit line actually resolved, not the
    # ones with a row of some kind for the period: a balance sheet stored
    # without an income statement is a symbol this screen cannot use, and
    # counting it would make the store look readier than it is.
    filed = len(symbols) - counts[GATE_NO_FILING] - counts[GATE_CONCEPT_UNKNOWN]
    coverage = filed / len(symbols)
    window_end = max(item.candidate.window_end for item in ranked)

    headline = {
        "period": period,
        "priorPeriod": prior,
        "asOfSession": window_end.isoformat(),
        "screened": len(symbols),
        # The population the percentiles were taken over, and the cloud the
        # scatter draws. Without it "afterFilters" is a count out of a universe
        # most of whose members were never measurable.
        "measured": len(ranked),
        "afterFilters": len(matched),
        # Non-zero reasons only. The whole ordered ladder, zeros included, is in
        # the ``filters`` frame the reader gets.
        "excluded": {gate: counts[gate] for gate in GATES if counts[gate]},
        "top": [
            {
                "symbol": item.candidate.symbol,
                "growthPct": _pct(item.candidate.growth_pct),
                "relReturnPct": _pct(item.candidate.rel_return_pct),
                "dislocationRank": _ratio(item.dislocation_rank),
            }
            for item in top[:HEADLINE_TOP]
        ],
    }

    return StudyResult(
        headline=headline,
        frames={
            "tiles": _tiles_frame(len(symbols), len(ranked), len(matched), period),
            "scatter": _scatter_frame(ranked),
            "ranking": _ranking_frame(top),
            "filters": _filters_frame(
                counts,
                universe=params.universe,
                screened=len(symbols),
                period=period,
                prior=prior,
                min_growth_pct=params.min_profit_growth_pct,
                max_price_change_pct=params.max_price_change_pct,
            ),
        },
        provenance=Provenance(
            source="vnstock",
            as_of=context.as_of,
            # The window every return was measured over, rather than the calendar
            # span read to find it: the read reaches back far enough to hold a
            # month of sessions, and the measurement is these closes.
            sessions_used=WINDOW_CLOSES,
            health="normal" if coverage >= HEALTHY_FILING_COVERAGE else "degraded",
            reason="; ".join(
                (
                    *(
                        ()
                        if coverage >= HEALTHY_FILING_COVERAGE
                        else (
                            f"store chỉ có báo cáo {period} cho {filed}/"
                            f"{len(symbols)} mã",
                        )
                    ),
                    *METHOD_NOTES,
                )
            ),
        ),
    )


# -- the universe, the period, and the two reads ---------------------------


def _universe(
    session: Session, kind: Universe, declared: Sequence[str]
) -> tuple[str, ...]:
    """Which symbols the screen starts from, alphabetically.

    The market roster rather than the declared Universe by default: a screen
    over thirty names is a table, and the question this Study answers is which
    of the market's companies stand out.
    """
    if kind == "declared":
        return tuple(sorted(declared))
    return ListingRosterStore(session).listed_symbols()


def _default_period(session: Session) -> str | None:
    """The newest quarter the store has filed widely enough to screen.

    Counted on the one line every gate below depends on rather than on any row
    of the period: a symbol whose balance sheet arrived and whose income
    statement did not is a symbol this screen cannot use, and counting it would
    make a quarter look ready before it is.

    Periods sort correctly as text (``2026-Q2`` > ``2026-Q1`` > ``2025-Q4``), so
    "newest" needs no parsing — the same property ``financial/reads.py`` rests on.
    """
    rows = session.execute(
        select(
            FinancialStatementLine.period,
            func.count(func.distinct(FinancialStatementLine.symbol)),
        )
        .where(
            FinancialStatementLine.statement == templates.NET_PROFIT_ITEM[0],
            FinancialStatementLine.item_id == templates.NET_PROFIT_ITEM[1],
            FinancialStatementLine.item_seq == financial_reads.PRIMARY_SEQ,
        )
        .group_by(FinancialStatementLine.period)
        .order_by(FinancialStatementLine.period.desc())
        .limit(PERIODS_CONSIDERED)
    ).all()
    if not rows:
        return None

    fullest = max(count for _, count in rows)
    # Newest first, and the fullest quarter satisfies its own share, so this
    # always answers.
    return next(
        period
        for period, count in rows
        if count >= PERIOD_COVERAGE_SHARE * fullest
    )


def _prior_period(period: str) -> str:
    """The same quarter one year earlier, which is what a YoY reading needs."""
    year, quarter = period.split("-Q")
    return f"{int(year) - 1}-Q{quarter}"


def _price_windows(
    session: Session, symbols: Sequence[str], as_of: datetime
) -> dict[str, tuple[_Close, ...]]:
    """The market's recent closed sessions, per symbol, oldest first.

    One query for the whole universe. Per symbol it would be fifteen hundred
    round trips for a screen that has to answer inside a tool round, which is
    the reason this read is here rather than expressed through
    :mod:`reads_daily` — that module answers about one symbol, deliberately.

    The closed-session rule is the same one every reader in this system keeps:
    today's half-finished session is excluded until the market has settled, so a
    twenty-session return does not change under the reader.
    """
    local = as_of.astimezone(VN_TZ)
    statement = select(
        BarDaily.symbol,
        BarDaily.trading_day,
        BarDaily.close,
        BarDaily.volume,
        BarDaily.price_basis,
    ).where(
        BarDaily.series == SERIES_EQUITY,
        BarDaily.symbol.in_(list(symbols)),
        BarDaily.trading_day >= local.date() - timedelta(days=CALENDAR_LOOKBACK_DAYS),
    )
    if local.time() < SESSION_SETTLED_AT:
        statement = statement.where(BarDaily.trading_day < local.date())

    grouped: dict[str, list[_Close]] = {}
    for symbol, day, close, volume, basis in session.execute(
        statement.order_by(BarDaily.symbol.asc(), BarDaily.trading_day.asc())
    ).all():
        grouped.setdefault(symbol, []).append(
            _Close(
                trading_day=day,
                close=float(close),
                volume=int(volume),
                price_basis=basis,
            )
        )
    return {symbol: tuple(closes) for symbol, closes in grouped.items()}


def _index_window(session: Session, as_of: datetime) -> _IndexWindow:
    """VN-Index over the same calendar span, oldest first.

    Read once for the whole screen. The refusal when it is short is about the
    store and says so: without the index there is no relative return, and an
    absolute return presented in its place would answer a different question
    than the one asked.
    """
    local = as_of.astimezone(VN_TZ)
    statement = select(BarDaily.trading_day, BarDaily.close).where(
        BarDaily.series == SERIES_INDEX,
        BarDaily.symbol == INDEX_SYMBOL,
        BarDaily.trading_day >= local.date() - timedelta(days=CALENDAR_LOOKBACK_DAYS),
    )
    if local.time() < SESSION_SETTLED_AT:
        statement = statement.where(BarDaily.trading_day < local.date())

    rows = session.execute(statement.order_by(BarDaily.trading_day.asc())).all()
    if len(rows) < WINDOW_CLOSES:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS,
            f"the store holds {len(rows)} closed {INDEX_SYMBOL} sessions in the "
            f"last {CALENDAR_LOOKBACK_DAYS} days, {WINDOW_CLOSES} needed to "
            f"measure a {REACTION_SESSIONS}-session return against the market",
        )
    return _IndexWindow(
        days=tuple(day for day, _ in rows),
        closes=tuple(float(close) for _, close in rows),
    )


# -- one symbol through the measurement gates ------------------------------


def _measure(
    symbol: str,
    current: Mapping[Concept, ConceptValue] | None,
    previous: Mapping[Concept, ConceptValue] | None,
    window: Sequence[_Close],
    index: _IndexWindow,
) -> str | _Candidate:
    """A candidate, or the name of the first gate this symbol failed.

    Growth needs a positive base on both sides. A percentage change out of a
    loss is a number a reader cannot use — it turns a swing from −100 to +50
    into "up 150%" — so a symbol with a non-positive quarter is excluded under
    its own name rather than ranked on an unusable figure.
    """
    if current is None:
        return GATE_NO_FILING
    net = current[Concept.NET_PROFIT]
    if net.value is None:
        return GATE_CONCEPT_UNKNOWN
    if previous is None:
        return GATE_NO_PRIOR_FILING
    base = previous[Concept.NET_PROFIT]
    if base.value is None:
        return GATE_PRIOR_CONCEPT_UNKNOWN

    profit = float(net.value)
    prior_profit = float(base.value)
    if profit <= 0:
        return GATE_NON_POSITIVE_PROFIT
    if prior_profit <= 0:
        return GATE_NON_POSITIVE_PRIOR_PROFIT

    if len(window) < WINDOW_CLOSES:
        # Both a 2025 listing and a symbol that stopped trading land here: what
        # the gate says is that the store has fewer than twenty-one closed
        # sessions for it inside the window read, which is true of both.
        return GATE_INSUFFICIENT_PRICE_HISTORY

    bars = tuple(window[-WINDOW_CLOSES:])
    first, last = bars[0], bars[-1]
    index_first = index.close_at(first.trading_day)
    index_last = index.close_at(last.trading_day)
    if (
        len({bar.price_basis for bar in bars}) > 1
        or first.close <= 0
        or index_first is None
        or index_last is None
        or index_first <= 0
    ):
        # Three guards under one name, and none of them has been observed: every
        # stored row is ``adjusted_at_source``, no close is zero, and the index
        # trades every session an equity does. They share a gate because they
        # share a consequence — the return over this window cannot be compared
        # with the market's.
        return GATE_PRICE_WINDOW_UNUSABLE

    adtv = float(median(bar.close * bar.volume for bar in bars))
    if adtv < LIQUIDITY_FLOOR_VND:
        return GATE_THIN_LIQUIDITY

    return_pct = (last.close / first.close - 1) * 100
    index_return_pct = (index_last / index_first - 1) * 100
    return _Candidate(
        symbol=symbol,
        net_profit_vnd=profit,
        prior_net_profit_vnd=prior_profit,
        growth_pct=(profit / prior_profit - 1) * 100,
        return_pct=return_pct,
        index_return_pct=index_return_pct,
        rel_return_pct=return_pct - index_return_pct,
        adtv_vnd=adtv,
        window_end=last.trading_day,
    )


# -- the composite ---------------------------------------------------------


def _rank(candidates: Sequence[_Candidate]) -> tuple[_Ranked, ...]:
    """Every candidate's standing on both axes, and the product of the two.

    The sample is every measurable symbol rather than the ones that passed the
    thresholds. A percentile taken over the survivors of a filter is a
    percentile of a group the filter defined: the top name would sit at 100 in
    every run whatever the market did.

    The price axis ranks the *negated* relative return, so the highest
    percentile belongs to the symbol whose price has followed least. Ties count
    as below on both axes, which is the convention
    ``signals/cross_sectional.percentile_of`` fixed for this system.

    Sorted by the composite, then by symbol. The tie-break is alphabetical
    rather than arbitrary because two symbols with identical percentiles have to
    come back in the same order on every run over the same store.
    """
    growths = [item.growth_pct for item in candidates]
    unfollowed = [-item.rel_return_pct for item in candidates]

    ranked = []
    for item in candidates:
        growth_standing = percentile_of(item.growth_pct, growths) / 100
        price_standing = percentile_of(-item.rel_return_pct, unfollowed) / 100
        ranked.append(
            _Ranked(
                candidate=item,
                growth_percentile=growth_standing,
                rel_return_percentile=price_standing,
                dislocation_rank=growth_standing * price_standing,
            )
        )
    return tuple(
        sorted(
            ranked,
            key=lambda item: (-item.dislocation_rank, item.candidate.symbol),
        )
    )


def _apply_thresholds(
    ranked: Sequence[_Ranked], min_growth_pct: float, max_price_change_pct: float
) -> tuple[tuple[_Ranked, ...], dict[str, int]]:
    """The rows that pass both thresholds, and how many each one removed.

    Counted in the gates' declared order — growth first — so a symbol failing
    both is counted once, under the first. That is what keeps the ladder in the
    ``filters`` frame an arithmetic that adds up.
    """
    matched: list[_Ranked] = []
    counts = dict.fromkeys(THRESHOLD_GATES, 0)
    for item in ranked:
        if item.candidate.growth_pct < min_growth_pct:
            counts[GATE_BELOW_GROWTH_THRESHOLD] += 1
        elif item.candidate.rel_return_pct > max_price_change_pct:
            counts[GATE_ABOVE_PRICE_CHANGE] += 1
        else:
            matched.append(item)
    return tuple(matched), counts


def quadrant_of(
    growth_pct: float,
    rel_return_pct: float,
    *,
    mid_growth: float,
    mid_rel: float,
) -> str:
    """Which named region of the scatter a point falls in.

    The dividers are the medians of what is plotted, which is what the widget
    draws its reference lines at (``components/signal_desk/widgets/
    scatter-quadrant.tsx``). Computed here as well so the region a point is in
    travels with the point in the artifact, rather than being a thing only the
    browser knows.
    """
    if growth_pct >= mid_growth:
        return (
            QUADRANT_HIGH_GROWTH_HIGH_PRICE
            if rel_return_pct >= mid_rel
            else QUADRANT_HIGH_GROWTH_LOW_PRICE
        )
    return (
        QUADRANT_LOW_GROWTH_HIGH_PRICE
        if rel_return_pct >= mid_rel
        else QUADRANT_LOW_GROWTH_LOW_PRICE
    )


# -- frames ----------------------------------------------------------------


def _tiles_frame(screened: int, measured: int, matched: int, period: str) -> Frame:
    return Frame(
        kind="table",
        columns=("label", "value", "unit"),
        rows=(
            ("Kỳ báo cáo", period, None),
            ("Số mã quét", screened, "mã"),
            ("Đo được cả hai trục", measured, "mã"),
            ("Qua cả hai ngưỡng", matched, "mã"),
        ),
        unit=None,
        labels={"label": "Chỉ số", "value": "Giá trị", "unit": "Đơn vị"},
    )


def _scatter_frame(ranked: Sequence[_Ranked]) -> Frame:
    """Every measurable symbol on the two axes, with the region it falls in.

    The whole cloud rather than the matches: the shape of the market is what
    makes a handful of names outliers, and a scatter of the winners is a picture
    with nothing to be far from.
    """
    growths = [item.candidate.growth_pct for item in ranked]
    relatives = [item.candidate.rel_return_pct for item in ranked]
    mid_growth = float(median(growths))
    mid_rel = float(median(relatives))
    return Frame(
        kind="table",
        columns=("symbol", "growth_pct", "rel_return_pct", "quadrant"),
        rows=tuple(
            (
                item.candidate.symbol,
                _pct(item.candidate.growth_pct),
                _pct(item.candidate.rel_return_pct),
                quadrant_of(
                    item.candidate.growth_pct,
                    item.candidate.rel_return_pct,
                    mid_growth=mid_growth,
                    mid_rel=mid_rel,
                ),
            )
            for item in ranked
        ),
        unit="%",
        labels={
            "symbol": "Mã",
            "growth_pct": "Tăng trưởng lợi nhuận so cùng kỳ (%)",
            "rel_return_pct": f"Lợi suất {REACTION_SESSIONS} phiên so VN-Index (%)",
            "quadrant": "Vùng",
        },
    )


def _ranking_frame(top: Sequence[_Ranked]) -> Frame:
    """The ranked rows with every input the composite was built from.

    Twelve columns because a ranking whose score cannot be recomputed from the
    row is a ranking a reader has to take on trust.
    """
    return Frame(
        kind="table",
        columns=(
            "rank",
            "symbol",
            "dislocation_rank",
            "growth_pct",
            "net_profit_vnd",
            "prior_net_profit_vnd",
            "rel_return_pct",
            "return_pct",
            "index_return_pct",
            "adtv_vnd",
            "growth_percentile",
            "rel_return_percentile",
        ),
        rows=tuple(
            (
                position,
                item.candidate.symbol,
                _ratio(item.dislocation_rank),
                _pct(item.candidate.growth_pct),
                _money(item.candidate.net_profit_vnd),
                _money(item.candidate.prior_net_profit_vnd),
                _pct(item.candidate.rel_return_pct),
                _pct(item.candidate.return_pct),
                _pct(item.candidate.index_return_pct),
                _money(item.candidate.adtv_vnd),
                _ratio(item.growth_percentile),
                _ratio(item.rel_return_percentile),
            )
            for position, item in enumerate(top, start=1)
        ),
        unit=None,
        labels={
            "rank": "Hạng",
            "symbol": "Mã",
            "dislocation_rank": "dislocation_rank",
            "growth_pct": "Tăng trưởng lợi nhuận so cùng kỳ (%)",
            "net_profit_vnd": "Lợi nhuận sau thuế kỳ này (VND)",
            "prior_net_profit_vnd": "Lợi nhuận sau thuế cùng kỳ (VND)",
            "rel_return_pct": f"Lợi suất {REACTION_SESSIONS} phiên so VN-Index (%)",
            "return_pct": f"Lợi suất {REACTION_SESSIONS} phiên (%)",
            "index_return_pct": f"VN-Index {REACTION_SESSIONS} phiên (%)",
            "adtv_vnd": "Trung vị giá × khối lượng (VND/phiên)",
            "growth_percentile": "Phân vị tăng trưởng",
            "rel_return_percentile": "Phân vị lợi suất tương đối đảo dấu",
        },
    )


def _filters_frame(
    counts: Mapping[str, int],
    *,
    universe: Universe,
    screened: int,
    period: str,
    prior: str,
    min_growth_pct: float,
    max_price_change_pct: float,
) -> Frame:
    """The ladder: what each gate asked for, what it removed, what was left.

    Every gate appears, including the ones that removed nothing, because a
    reader checking a screen needs to see that a gate ran — a row missing from
    this table reads as a gate nobody applied.
    """
    requirements = {
        GATE_NO_FILING: f"có báo cáo kỳ {period}",
        GATE_CONCEPT_UNKNOWN: "đọc được lợi nhuận sau thuế",
        GATE_NO_PRIOR_FILING: f"có báo cáo kỳ {prior}",
        GATE_PRIOR_CONCEPT_UNKNOWN: f"đọc được lợi nhuận sau thuế kỳ {prior}",
        GATE_NON_POSITIVE_PROFIT: "lợi nhuận kỳ này > 0",
        GATE_NON_POSITIVE_PRIOR_PROFIT: "lợi nhuận cùng kỳ > 0",
        GATE_INSUFFICIENT_PRICE_HISTORY: (
            f"≥ {WINDOW_CLOSES} phiên đã đóng trong {CALENDAR_LOOKBACK_DAYS} ngày"
        ),
        GATE_PRICE_WINDOW_UNUSABLE: (
            "cửa sổ giá cùng một Price Basis và so được với VN-Index"
        ),
        GATE_THIN_LIQUIDITY: (
            f"trung vị giá × khối lượng ≥ {LIQUIDITY_FLOOR_VND / 1e9:.0f} tỷ "
            "đồng/phiên"
        ),
        GATE_BELOW_GROWTH_THRESHOLD: f"tăng trưởng ≥ {_pct(min_growth_pct)}%",
        GATE_ABOVE_PRICE_CHANGE: (
            f"lợi suất so VN-Index ≤ {_pct(max_price_change_pct)}%"
        ),
    }
    described = (
        "market = mã đang niêm yết"
        if universe == "market"
        else "declared = Universe khai báo"
    )
    rows = [("universe", "Universe", described, 0, screened)]
    remaining = screened
    for gate in GATES:
        remaining -= counts[gate]
        rows.append(
            (gate, GATE_LABELS[gate], requirements[gate], counts[gate], remaining)
        )
    return Frame(
        kind="table",
        columns=("code", "gate", "requirement", "excluded", "remaining"),
        rows=tuple(rows),
        unit="mã",
        labels={
            "code": "Mã cửa",
            "gate": "Cửa lọc",
            "requirement": "Điều kiện",
            "excluded": "Số mã bị loại",
            "remaining": "Số mã còn lại",
        },
    )


def view(result: StudyResult) -> SignalDeskSpec:
    """Four blocks: the counts, the cloud, the ranking, the ladder.

    The scatter is the hero and the ranking sits under it, which is the opposite
    of what a reader wants and the right way round for what the data supports: a
    top-ten list read alone is a recommendation, and the same ten names read off
    a cloud of four hundred are ten points somebody can see the position of.

    The ladder is last and it is not an appendix. It is the block that answers
    "why is my symbol not here", which is the first question any screen gets.
    """
    period = result.headline["period"]
    return SignalDeskSpec(
        title=f"Lợi nhuận tăng, giá chưa theo — {period}",
        blocks=(
            SignalDeskBlock(
                widget="stat_tiles",
                widget_version=1,
                frame="tiles",
                options={"label": "label", "value": "value", "unit": "unit"},
            ),
            SignalDeskBlock(
                widget="scatter_quadrant",
                widget_version=1,
                frame="scatter",
                options={
                    "label": "symbol",
                    "x": "growth_pct",
                    "y": "rel_return_pct",
                },
            ),
            SignalDeskBlock(
                widget="ranked_bars",
                widget_version=1,
                frame="ranking",
                options={"label": "symbol", "value": "dislocation_rank"},
            ),
            SignalDeskBlock(
                widget="data_table",
                widget_version=1,
                frame="filters",
                options={},
            ),
        ),
    )


# -- readings a person will see -------------------------------------------


def _pct(value: float) -> float:
    """A rate at two decimals, which is more precision than any of them earns."""
    return round(value, 2)


def _ratio(value: float) -> float:
    """A percentile or a composite of two, at four decimals."""
    return round(value, 4)


def _money(value: float) -> float:
    """Dong at the width money is quoted in: whole units."""
    return float(Decimal(str(value)).quantize(Decimal("1")))


DEFINITION = register(
    StudyDefinition(
        name=NAME,
        version=VERSION,
        question=(
            "Mã nào có lợi nhuận quý tăng mạnh so với cùng kỳ mà giá "
            f"{REACTION_SESSIONS} phiên gần nhất chưa theo thị trường?"
        ),
        display_name="Lợi nhuận tăng, giá chưa theo",
        params_model=EarningsDislocationParams,
        # Nothing to warm. Every input is a market-wide store read: the filings
        # the quarterly scan writes and the daily bars the backfill writes. A
        # screen that fetched what it was missing would spend a tool round on
        # fifteen hundred provider calls, so a thin store is reported as a thin
        # store instead.
        requires=(),
        frames=("tiles", "scatter", "ranking", "filters"),
        widgets=(
            ("stat_tiles", 1),
            ("scatter_quadrant", 1),
            ("ranked_bars", 1),
            ("data_table", 1),
        ),
        compute=compute,
        view=view,
    )
)


__all__ = [
    "CALENDAR_LOOKBACK_DAYS",
    "DEFINITION",
    "GATES",
    "GATE_ABOVE_PRICE_CHANGE",
    "GATE_BELOW_GROWTH_THRESHOLD",
    "GATE_CONCEPT_UNKNOWN",
    "GATE_INSUFFICIENT_PRICE_HISTORY",
    "GATE_LABELS",
    "GATE_NON_POSITIVE_PRIOR_PROFIT",
    "GATE_NON_POSITIVE_PROFIT",
    "GATE_NO_FILING",
    "GATE_NO_PRIOR_FILING",
    "GATE_PRICE_WINDOW_UNUSABLE",
    "GATE_PRIOR_CONCEPT_UNKNOWN",
    "GATE_THIN_LIQUIDITY",
    "HEADLINE_TOP",
    "HEALTHY_FILING_COVERAGE",
    "LIQUIDITY_FLOOR_VND",
    "MEASUREMENT_GATES",
    "METHOD_NOTES",
    "NAME",
    "PERIOD_COVERAGE_SHARE",
    "QUADRANT_HIGH_GROWTH_HIGH_PRICE",
    "QUADRANT_HIGH_GROWTH_LOW_PRICE",
    "QUADRANT_LOW_GROWTH_HIGH_PRICE",
    "QUADRANT_LOW_GROWTH_LOW_PRICE",
    "REACTION_SESSIONS",
    "THRESHOLD_GATES",
    "TOP_N_CEILING",
    "TOP_N_FLOOR",
    "VERSION",
    "WINDOW_CLOSES",
    "EarningsDislocationParams",
    "compute",
    "quadrant_of",
    "view",
]
