"""A synthetic market of 45 symbols whose ranking is known before it runs.

The screen's composite is a product of two percentiles taken over the symbols it
could measure, and a percentile counts ties as below
(``signals/cross_sectional.percentile_of``). So over ``n`` candidates with
distinct values, a symbol standing ``i``-th from the bottom has percentile
``i/n`` exactly — and the whole ranking becomes arithmetic a reader can do on
paper:

    dislocation_rank = growth_rank × price_rank / n²

This file plants exactly that. Every candidate carries a distinct growth rank
and a distinct price rank, both from 1 to 33, so the expected order is the
descending order of ``growth_rank × price_rank``. The eight symbols that pass
both thresholds are given a deliberately *scrambled* pair of ranks
(:data:`EXPECTED_TOP`), so a ranking computed from either axis alone — or from
the two swapped — comes out in a different order and the test fails.

The numbers behind the ranks are as flat as the arithmetic allows:

* **Growth.** Every symbol's year-ago profit is :data:`PRIOR_PROFIT_VND` and its
  current profit is that plus ``growth_rank + 0.5`` percent, so ``growth_pct`` is
  the rank and a half — half a point clear of the twenty-percent floor, which no
  symbol may sit exactly on.
* **Price.** Every window is 21 sessions at :data:`BASE_CLOSE` with the last one
  moved, so the twenty-session return is exactly the move. VN-Index rises
  :data:`INDEX_RETURN_PCT` over the same 21 days, so a symbol's relative return
  is its move minus that — and ``rel_return_pct`` is ``17,5 − price_rank``,
  again clear of the five-point ceiling.
* **Liquidity.** Twenty of the 21 closes are :data:`BASE_CLOSE`, so the median of
  ``close × volume`` is ``BASE_CLOSE × volume`` with no rounding at all: 4 tỷ for
  a liquid symbol and 2 tỷ for a thin one, against a floor of 3.

Twelve symbols are planted to fail one gate each, one gate at a time, so the
exclusion counts are a designed fact rather than an observation. They still get
whatever the gates before theirs need — a thin symbol has both filings and a
full price window — so each one is excluded for its own reason and not by
accident.

The three statement templates are here because the screen must not depend on
which of them a company reports under. A bank and an industrial report a
labelled pretax line; a securities house reports none, and its pretax figure
arrives under ``business_income_tax_expenses`` where only the tax identity can
find it (``stocks/financial/templates.py``). All three report
``net_profit_loss_after_tax``, which is the line this screen reads, and the
fixture spreads the 45 symbols across all three.

The tickers are invented. A suite that wrote statements and sessions under real
tickers would leave numbers nothing verified sitting under names a reader
trusts, and would delete rows a market-wide scan collected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete

from src.stocks.financial import STATEMENT_INCOME
from src.stocks.models import BarDaily, FinancialStatementLine, ListingRoster
from src.stocks.providers.normalize import VN_TZ
from src.studies.reads_daily import INDEX_SYMBOL, SERIES_EQUITY, SERIES_INDEX

SOURCE = "vnstock"
PRICE_BASIS = "adjusted_at_source"

#: The quarter screened, the one it is compared against, and a newer quarter
#: only a handful of companies have filed — which is what the default period
#: rule has to see through.
PERIOD = "2026-Q2"
PRIOR_PERIOD = "2025-Q2"
HALF_FILED_PERIOD = "2026-Q3"
HALF_FILED_SYMBOLS = 3

#: The window: 21 consecutive days ending here, and an as-of after its close so
#: the last session counts as settled.
LAST_SESSION = date(2026, 8, 21)
SESSIONS = 21
AS_OF = datetime(2026, 8, 21, 16, 0, tzinfo=VN_TZ)

BASE_CLOSE = 10_000
INDEX_OPEN = 1_000.0
INDEX_LAST = 1_020.0
INDEX_RETURN_PCT = 2.0

#: Volumes either side of the three-billion floor, at a close of 10.000đ.
LIQUID_VOLUME = 400_000
THIN_VOLUME = 200_000

PRIOR_PROFIT_VND = 100e9

TEMPLATE_BANK = "bank"
TEMPLATE_SECURITIES = "securities"
TEMPLATE_INDUSTRIAL = "industrial"
TEMPLATES = (TEMPLATE_BANK, TEMPLATE_SECURITIES, TEMPLATE_INDUSTRIAL)

#: The gate each planted exclusion is meant to fail, in the study's own
#: vocabulary. Kept as strings rather than imported so a rename of a gate shows
#: up as a failing test rather than as a fixture that silently followed it.
GATE_NO_FILING = "no_filing"
GATE_CONCEPT_UNKNOWN = "concept_unknown"
GATE_NO_PRIOR_FILING = "no_prior_filing"
GATE_PRIOR_CONCEPT_UNKNOWN = "prior_concept_unknown"
GATE_NON_POSITIVE_PROFIT = "non_positive_profit"
GATE_NON_POSITIVE_PRIOR_PROFIT = "non_positive_prior_profit"
GATE_INSUFFICIENT_PRICE_HISTORY = "insufficient_price_history"
GATE_THIN_LIQUIDITY = "thin_liquidity"


@dataclass(frozen=True)
class Candidate:
    """A symbol the screen can measure, and where it stands on both axes."""

    symbol: str
    growth_rank: int
    price_rank: int

    @property
    def growth_pct(self) -> float:
        """The rank, plus half a point.

        The half point is the difference between a fixture and a coin toss. A
        growth of exactly 20 against a floor of exactly 20 is decided by whether
        ``1.2 - 1`` is a shade under or over ``0.2`` in binary — the screen's
        comparison is correct either way and the *count* it produces would move
        under a change nobody made. The same half point keeps every relative
        return clear of the price ceiling.
        """
        return self.growth_rank + 0.5

    @property
    def rel_return_pct(self) -> float:
        return 17.5 - self.price_rank

    @property
    def return_pct(self) -> float:
        return self.rel_return_pct + INDEX_RETURN_PCT

    @property
    def net_profit_vnd(self) -> float:
        return PRIOR_PROFIT_VND * (1 + self.growth_pct / 100)

    @property
    def dislocation_rank(self) -> float:
        return self.growth_rank * self.price_rank / CANDIDATE_COUNT**2


@dataclass(frozen=True)
class Excluded:
    """A symbol planted to fail exactly one gate."""

    symbol: str
    gate: str


#: The eight symbols that pass both thresholds, with the scrambled rank pairs
#: that decide their order. Growth ranks 26–33 and price ranks 26–33, paired so
#: that neither axis alone produces the expected order.
MATCHING = (
    Candidate("ZZE07", growth_rank=33, price_rank=30),
    Candidate("ZZE21", growth_rank=32, price_rank=33),
    Candidate("ZZE04", growth_rank=31, price_rank=32),
    Candidate("ZZE33", growth_rank=30, price_rank=31),
    Candidate("ZZE12", growth_rank=29, price_rank=29),
    Candidate("ZZE29", growth_rank=28, price_rank=26),
    Candidate("ZZE16", growth_rank=27, price_rank=28),
    Candidate("ZZE41", growth_rank=26, price_rank=27),
)

#: The order those eight come back in: ``growth_rank × price_rank`` descending.
#: 1056, 992, 990, 930, 841, 756, 728, 702 — no two alike, so nothing here rests
#: on a tie-break.
EXPECTED_TOP = ("ZZE21", "ZZE04", "ZZE07", "ZZE33", "ZZE12", "ZZE16", "ZZE29", "ZZE41")

#: The 25 symbols that are measured and then filtered out: nineteen whose growth
#: is under the twenty-percent floor, and six whose price has already outrun the
#: market by more than five points. Their ranks are 1–25 on both axes, so the
#: largest product among them (475) is below the smallest among the matches
#: (702) — the background cannot reach the ranking however the thresholds move.
_BACKGROUND_IDS = (
    "01", "03", "06", "08", "10", "13", "15", "17", "19", "20", "22", "24",
    "25", "26", "28", "30", "32", "34", "35", "37", "39", "40", "42", "43", "44",
)

BACKGROUND = tuple(
    Candidate(
        symbol=f"ZZE{identifier}",
        growth_rank=growth_rank,
        # Under the growth floor: spread across the middle of the price axis.
        # At or over it: pushed to the top of the price axis, where the relative
        # return is above the five-point ceiling and the price gate is what
        # removes them.
        price_rank=growth_rank + 6 if growth_rank <= 19 else 26 - growth_rank,
    )
    for growth_rank, identifier in enumerate(_BACKGROUND_IDS, start=1)
)

CANDIDATES = MATCHING + BACKGROUND
CANDIDATE_COUNT = len(CANDIDATES)

#: How many candidates each threshold removes, by construction: growth ranks
#: 1–19 fail the growth floor, ranks 20–25 clear it and fail the price ceiling.
BELOW_GROWTH = 19
ABOVE_PRICE_CHANGE = 6

#: One symbol per gate, twice over where a single case would leave the count
#: indistinguishable from an off-by-one.
EXCLUSIONS = (
    Excluded("ZZE02", GATE_NO_FILING),
    Excluded("ZZE45", GATE_NO_FILING),
    Excluded("ZZE09", GATE_CONCEPT_UNKNOWN),
    Excluded("ZZE14", GATE_NO_PRIOR_FILING),
    Excluded("ZZE38", GATE_NO_PRIOR_FILING),
    Excluded("ZZE23", GATE_PRIOR_CONCEPT_UNKNOWN),
    Excluded("ZZE05", GATE_NON_POSITIVE_PROFIT),
    Excluded("ZZE31", GATE_NON_POSITIVE_PROFIT),
    Excluded("ZZE18", GATE_NON_POSITIVE_PRIOR_PROFIT),
    Excluded("ZZE27", GATE_INSUFFICIENT_PRICE_HISTORY),
    Excluded("ZZE11", GATE_THIN_LIQUIDITY),
    Excluded("ZZE36", GATE_THIN_LIQUIDITY),
)

EXCLUDED_COUNTS = {
    gate: sum(1 for item in EXCLUSIONS if item.gate == gate)
    for gate in {item.gate for item in EXCLUSIONS}
}

SYMBOLS = tuple(item.symbol for item in CANDIDATES) + tuple(
    item.symbol for item in EXCLUSIONS
)
SCREENED = len(SYMBOLS)


def sessions() -> list[date]:
    """The 21 consecutive days the window is built on, oldest first.

    ``bar_daily`` holds whatever sessions the provider answered with and keeps
    no calendar of its own, so a run of calendar days is a valid window and one
    fewer thing a reader of the golden numbers has to reconstruct.
    """
    return [
        LAST_SESSION - timedelta(days=offset)
        for offset in range(SESSIONS - 1, -1, -1)
    ]


def load(session) -> None:
    """Everything the screen reads: the roster, the sessions, the filings."""
    clear(session)
    _load_bars(session)
    _load_statements(session)


def load_roster(session) -> None:
    """The listing register, for the one path that screens the market itself."""
    clear_roster(session)
    session.add_all(
        ListingRoster(
            symbol=symbol,
            exchange="HOSE",
            is_listed=True,
            company_name=f"Công ty {symbol}",
            source=SOURCE,
            observed_at=AS_OF,
        )
        for symbol in SYMBOLS
    )


def _load_bars(session) -> None:
    days = sessions()
    session.add_all(
        _bar(INDEX_SYMBOL, day, close, 0, series=SERIES_INDEX)
        for day, close in zip(days, _index_closes())
    )
    for candidate in CANDIDATES:
        session.add_all(
            _bar(candidate.symbol, day, close, LIQUID_VOLUME)
            for day, close in zip(days, _closes(candidate.return_pct))
        )
    for item in EXCLUSIONS:
        # A short window for the one symbol whose gate is the window, a full one
        # for everybody else: an exclusion has to be the gate it was planted for
        # rather than the first gate a missing input happens to trip.
        kept = SESSIONS - 1 if item.gate == GATE_INSUFFICIENT_PRICE_HISTORY else SESSIONS
        volume = THIN_VOLUME if item.gate == GATE_THIN_LIQUIDITY else LIQUID_VOLUME
        session.add_all(
            _bar(item.symbol, day, close, volume)
            for day, close in zip(days[-kept:], _closes(0.0)[-kept:])
        )


def _index_closes() -> list[float]:
    """The market's window: flat, then the move that makes the index return."""
    return [INDEX_OPEN] * (SESSIONS - 1) + [INDEX_LAST]


def _closes(return_pct: float) -> list[float]:
    """A window whose only move is the last session's.

    Twenty closes at :data:`BASE_CLOSE` and one at the end, so the return over
    the window is exactly ``return_pct`` and the median of ``close × volume`` is
    exactly ``BASE_CLOSE × volume``.
    """
    return [float(BASE_CLOSE)] * (SESSIONS - 1) + [
        BASE_CLOSE * (1 + return_pct / 100)
    ]


def _bar(
    symbol: str,
    day: date,
    close: float,
    volume: int,
    *,
    series: str = SERIES_EQUITY,
) -> BarDaily:
    return BarDaily(
        symbol=symbol,
        trading_day=day,
        series=series,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        price_basis=PRICE_BASIS,
        source=SOURCE,
        observed_at=AS_OF,
    )


def _load_statements(session) -> None:
    for index, candidate in enumerate(CANDIDATES):
        template = TEMPLATES[index % len(TEMPLATES)]
        _income(session, candidate.symbol, PERIOD, candidate.net_profit_vnd, template)
        _income(session, candidate.symbol, PRIOR_PERIOD, PRIOR_PROFIT_VND, template)

    for index, item in enumerate(EXCLUSIONS):
        template = TEMPLATES[index % len(TEMPLATES)]
        _statements_for_gate(session, item, template)

    # A newer quarter a handful of early filers have reported. The default
    # period rule has to prefer the quarter the market has finished.
    for candidate in CANDIDATES[:HALF_FILED_SYMBOLS]:
        _income(
            session,
            candidate.symbol,
            HALF_FILED_PERIOD,
            candidate.net_profit_vnd,
            TEMPLATE_INDUSTRIAL,
        )


def _statements_for_gate(session, item: Excluded, template: str) -> None:
    """The filings a planted exclusion needs to reach its own gate."""
    if item.gate == GATE_NO_FILING:
        return
    if item.gate == GATE_CONCEPT_UNKNOWN:
        # An income statement with no net-profit line in it: the filing is
        # stored and the concept is unknown, which is the distinction the
        # resolver exists to make.
        _income(session, item.symbol, PERIOD, None, template)
        _income(session, item.symbol, PRIOR_PERIOD, PRIOR_PROFIT_VND, template)
        return
    if item.gate == GATE_NO_PRIOR_FILING:
        _income(session, item.symbol, PERIOD, PRIOR_PROFIT_VND * 2, template)
        return
    if item.gate == GATE_PRIOR_CONCEPT_UNKNOWN:
        _income(session, item.symbol, PERIOD, PRIOR_PROFIT_VND * 2, template)
        _income(session, item.symbol, PRIOR_PERIOD, None, template)
        return
    if item.gate == GATE_NON_POSITIVE_PROFIT:
        # Zero for one of the two and a loss for the other: both are quarters a
        # percentage change cannot be taken out of.
        loss = 0.0 if item.symbol == "ZZE05" else -50e9
        _income(session, item.symbol, PERIOD, loss, template)
        _income(session, item.symbol, PRIOR_PERIOD, PRIOR_PROFIT_VND, template)
        return
    if item.gate == GATE_NON_POSITIVE_PRIOR_PROFIT:
        _income(session, item.symbol, PERIOD, PRIOR_PROFIT_VND, template)
        _income(session, item.symbol, PRIOR_PERIOD, -20e9, template)
        return
    _income(session, item.symbol, PERIOD, PRIOR_PROFIT_VND * 2, template)
    _income(session, item.symbol, PRIOR_PERIOD, PRIOR_PROFIT_VND, template)


def _income(
    session, symbol: str, period: str, net_profit: float | None, template: str
) -> None:
    """One quarter's income statement in the shape its template reports it.

    ``net_profit`` of ``None`` writes the statement without the line the screen
    reads — a filing that is stored and cannot answer, which is not the same
    thing as a filing that is absent.
    """
    lines: dict[str, float] = {}
    if net_profit is not None:
        lines["net_profit_loss_after_tax"] = net_profit
    tax_current = -10e9
    tax_deferred = -2e9
    pretax = (net_profit or 0.0) - tax_current - tax_deferred

    if template == TEMPLATE_SECURITIES:
        # No labelled pretax line at all. The figure arrives under the tax
        # expense id and only the tax identity can recognise it.
        lines["business_income_tax_expenses"] = pretax
        lines["business_income_tax_current"] = tax_current
        lines["business_income_tax_deferred"] = tax_deferred
    else:
        lines["net_accounting_profit_loss_before_tax"] = pretax

    session.add_all(
        FinancialStatementLine(
            symbol=symbol,
            period=period,
            statement=STATEMENT_INCOME,
            item_id=item_id,
            item_seq=0,
            value=value,
            source=SOURCE,
            observed_at=AS_OF,
        )
        for item_id, value in lines.items()
    )


def clear(session) -> None:
    session.execute(delete(BarDaily).where(BarDaily.symbol.in_(SYMBOLS)))
    # The index is a real ticker whose rows a market-wide backfill writes, so
    # only the window this fixture planted is removed.
    session.execute(
        delete(BarDaily)
        .where(BarDaily.symbol == INDEX_SYMBOL)
        .where(BarDaily.trading_day.in_(sessions()))
    )
    session.execute(
        delete(FinancialStatementLine).where(
            FinancialStatementLine.symbol.in_(SYMBOLS)
        )
    )
    clear_roster(session)


def clear_roster(session) -> None:
    session.execute(delete(ListingRoster).where(ListingRoster.symbol.in_(SYMBOLS)))


__all__ = [
    "ABOVE_PRICE_CHANGE",
    "AS_OF",
    "BACKGROUND",
    "BASE_CLOSE",
    "BELOW_GROWTH",
    "CANDIDATES",
    "CANDIDATE_COUNT",
    "EXCLUDED_COUNTS",
    "EXCLUSIONS",
    "EXPECTED_TOP",
    "HALF_FILED_PERIOD",
    "INDEX_RETURN_PCT",
    "LAST_SESSION",
    "MATCHING",
    "PERIOD",
    "PRIOR_PERIOD",
    "PRIOR_PROFIT_VND",
    "SCREENED",
    "SESSIONS",
    "SYMBOLS",
    "Candidate",
    "Excluded",
    "clear",
    "clear_roster",
    "load",
    "load_roster",
    "sessions",
]
