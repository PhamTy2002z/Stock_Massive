"""Three results figures, read out of the quarterly statement store.

Every other field in this package is a function of sessions. These three are a
function of filings, and they are here because the store already holds them:
302.528 lines over 1.235 symbols and 34 quarters from 2018-Q1 (measured
2026-08-28), and until now not one **Signal Field** read any of it.

## Why these three lines and not the obvious ones

Because the obvious ones are not in the store. A revenue line is not a line at
all in this table — it arrives under the template of the industry that filed it
(``revenue_in_brokerage_services``, ``net_revenue_of_insurance_premium``,
``revenue_from_real_estate_investment``), and ``net_revenue`` itself has **zero**
rows. A margin is the same story a division later. The three lines below were
chosen the other way round: measured first, declared second.

| line | symbols | quarters |
|---|---|---|
| ``eps_basic_vnd`` | 1.235 | 34 |
| ``net_profit_loss_after_tax`` | 1.222 | 34 |
| ``gross_profit`` | 1.192 | 34 |

They are cross-industry lines, which is what makes them serveable at all — but
"cross-industry" is not "universal", and the gap is measured rather than assumed:
in 2026-Q2, thirty symbols file a net profit and no gross profit, and every one
of them is a credit institution — twenty-eight banks and two finance companies,
which file the same statement form. One asked for a gross-profit trend gets
``statement_line_missing``, which is the truth about its filing rather than a
zero standing in for one.

## An exact zero is a line that was not filed

The store cannot tell an unreported line from a reported zero: both arrive as
``0.0000``. Which way to read it is decided by measurement, not by taste —
**2.491 of 9.536** ``eps_basic_vnd`` rows are exactly zero, and the filings they
sit in carry trillions of net profit (BID, CTG, MBB, TCB and HPG all report a
2026-Q2 profit in the trillions and an EPS of exactly zero). Meanwhile **zero**
of 9.432 ``net_profit_loss_after_tax`` rows are zero, so nothing is lost by
reading a zero the same way everywhere.

So :meth:`QuarterlyStatements.income_line` answers ``None`` for an exact zero and
the reading refuses by name. Read the other way, a company whose provider stopped
reporting EPS would print a year-on-year fall of exactly −100% — a number that
looks like a collapse in the business and is a gap in a feed.

## The cutoff decides which quarters existed

The quarters read are the ones whose quarter **ends** at or before the window's
newest session, because a window answered for an old date must not acquire
filings nobody had then — the same rule
``fundamentals.fundamentals_on_or_before`` keeps for the snapshot store. It is a
quarter-boundary rule and not a filing-lag rule, and that is a limit rather than
a choice: this table records when a row was *collected*, and the whole store was
backfilled at once, so it holds no date on which a filing became public.

Nothing here opens a query of its own. The statements arrive on the
``FieldWindow`` the way the foreign-share flows do — the field declares that it
needs them and ``serving`` loads them — because a field that reached past that
object for data would be the second path to a store that one gateway exists to
make impossible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.stocks.financial import STATEMENT_INCOME
from src.stocks.financial.reads import lines_for, periods_for

from .fields import FieldReading, FieldWindow
from .fundamentals import FUNDAMENTAL_STALE_DAYS
from .issues import SignalIssue

#: The floor these fields refuse below: one session with a traded quantity.
#:
#: A filing is not a session, so the window is not an input here — it is what
#: dates the read. One session is what the gateway needs to hand back a cutoff
#: at all, and demanding more would refuse a results figure for a reason that
#: has nothing to do with results.
EARNINGS_MIN_SESSIONS = 1

#: How far back the window may look for that one session: a trading week.
#:
#: A symbol that did not trade today still filed its quarter, and refusing it
#: would be the declaration causing the refusal rather than the store. The
#: tolerance is safe in one direction only, which is the direction that matters:
#: an older cutoff can only drop a quarter whose end it now precedes, and a
#: quarter that has just ended has not been filed yet anyway.
EARNINGS_LOOKBACK_SESSIONS = 5

#: How many quarters ``serving`` loads for a field that asked for statements.
#:
#: Five, and the fifth is the whole point: a year-on-year reading compares a
#: quarter with the same quarter four back, so four would put the comparison
#: exactly one quarter out of reach. Bounded rather than "all of them" because
#: each quarter is its own read of a statement that runs 25 to 208 lines.
QUARTERS_READ = 5

#: How many quarters the gross-profit trend is fitted over.
#:
#: Four: the shortest run in which one of each season appears, which is as much
#: as a slope over consecutive quarters can do about seasonality.
TREND_QUARTERS = 4

EPS_BASIC_ITEM = "eps_basic_vnd"
NET_PROFIT_ITEM = "net_profit_loss_after_tax"
GROSS_PROFIT_ITEM = "gross_profit"

#: The last day of each quarter, which is the date a period text stands for.
_QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

#: The keys these fields return beside a number or a refusal. Declared on each
#: field so the descriptive bar can be checked against them at import.
YEAR_ON_YEAR_KEYS = (
    "period",
    "prior_period",
    "period_age_days",
    "statement_line",
    "current_figure",
    "prior_year_figure",
)

TREND_KEYS = (
    "period",
    "periods",
    "period_age_days",
    "statement_line",
    "average_level_vnd",
    "slope_vnd_per_quarter",
)


def quarter_end(period: str) -> date:
    """The date a period text stands for: ``2026-Q2`` is 30 June 2026.

    Periods sort correctly as text and need no parsing to order
    (``financial/reads.py``), but they do need parsing to be compared with a
    session — and "which quarters existed on this date" is exactly that
    comparison.
    """
    year, quarter = period.split("-Q")
    month, day = _QUARTER_END[int(quarter)]
    return date(int(year), month, day)


def previous_period(period: str) -> str:
    """The quarter immediately before this one."""
    year, quarter = period.split("-Q")
    index = int(quarter)
    if index == 1:
        return f"{int(year) - 1}-Q4"
    return f"{year}-Q{index - 1}"


def prior_year_period(period: str) -> str:
    """The same quarter one year earlier, which is what a YoY reading needs.

    The same quarter rather than the previous one, because a Vietnamese
    issuer's quarters are not comparable with each other: a property developer
    hands over in Q4 and a retailer sells in Q1, so Q2-against-Q1 measures the
    calendar and Q2-against-Q2 measures the company.
    """
    year, quarter = period.split("-Q")
    return f"{int(year) - 1}-Q{quarter}"


@dataclass(frozen=True)
class QuarterlyStatements:
    """One symbol's newest income statements at a cutoff, newest period first.

    The quarterly twin of ``FundamentalStanding``: a fact that is not a session,
    loaded by ``serving`` because a field declared that it needs one. It holds
    whole statements rather than named figures, because which line answers a
    question is the field's business — two fields over the same filing disagree
    about whether it is answerable, and that disagreement is the information.
    """

    symbol: str
    #: The window's newest session. Every period here ends at or before it.
    cutoff: date
    #: Newest first, the way the store's index hands them back.
    periods: tuple[str, ...]
    lines: Mapping[str, Mapping[tuple[str, str], Decimal]]

    @property
    def newest(self) -> str:
        """The newest quarter stored at or before the cutoff."""
        return self.periods[0]

    def income_line(self, period: str, item_id: str) -> float | None:
        """One income-statement line as a number, or ``None`` for no line.

        An exact zero answers ``None``. The store holds an unreported line and a
        reported zero identically, and the measurement at the top of this module
        says which one a zero almost always is: a quarter read as zero profit is
        a gap in a feed narrated as a collapse in a business.
        """
        value = self.lines.get(period, {}).get((STATEMENT_INCOME, item_id))
        if value is None or value == 0:
            return None
        return float(value)

    def age_days(self, period: str) -> int:
        """How old this quarter is at the cutoff, in days.

        The caveat that matters for a stored figure is its age, not an error bar
        (``fields.FieldSource``), and a Q2 number narrated in November is wrong
        in a way no threshold catches.
        """
        return (self.cutoff - quarter_end(period)).days


def quarterly_statements_for(
    session: Session,
    symbol: str,
    cutoff: date,
    *,
    quarters: int = QUARTERS_READ,
) -> QuarterlyStatements | None:
    """The newest income statements filed at or before a date, or nothing.

    ``None`` where the store holds no income statement for this symbol at all at
    or before the cutoff, which is the same shape ``fundamentals_on_or_before``
    keeps: an empty standing invented for a symbol with no filing would make
    "nothing collected" and "collected and empty" indistinguishable, and those
    two send a reader to two different places.

    One index read for the periods and one statement read per period. Bounded by
    ``quarters`` rather than open-ended, because a statement is 25 to 208 lines
    and a field needs five quarters of them at most.
    """
    stored = periods_for(session, symbol, statement=STATEMENT_INCOME)
    usable = tuple(
        period for period in stored if quarter_end(period) <= cutoff
    )[:quarters]
    if not usable:
        return None
    return QuarterlyStatements(
        symbol=symbol.upper(),
        cutoff=cutoff,
        periods=usable,
        lines={period: lines_for(session, symbol, period) for period in usable},
    )


def eps_basic_yoy_reading(window: FieldWindow) -> FieldReading:
    """Basic earnings per share against the same quarter one year earlier."""
    return _year_on_year(window, EPS_BASIC_ITEM)


def net_profit_yoy_reading(window: FieldWindow) -> FieldReading:
    """Net profit after tax against the same quarter one year earlier."""
    return _year_on_year(window, NET_PROFIT_ITEM)


def gross_profit_trend_reading(window: FieldWindow) -> FieldReading:
    """The gross-profit slope over four quarters, per quarter, against its level.

    A slope rather than a first-to-last change, so no single quarter decides the
    answer, and scaled by the four quarters' own average so a trillion-dong
    company and a billion-dong one are comparable at all. The result is
    percent of its own average level per quarter, and it is signed: a business
    whose gross profit is contracting has a negative one.

    Four **consecutive** quarters, and a hole refuses rather than closes: a
    slope fitted over Q3, Q1 and Q2 with Q4 missing is a slope over a different
    series wearing this one's name.
    """
    statements = window.quarterly
    if statements is None:
        return FieldReading(
            value=None,
            refusal=SignalIssue.FUNDAMENTAL_NOT_STORED,
            extras={"statement_line": GROSS_PROFIT_ITEM},
        )

    period = statements.newest
    wanted: list[str] = [period]
    while len(wanted) < TREND_QUARTERS:
        wanted.append(previous_period(wanted[-1]))
    run = tuple(reversed(wanted))
    extras = {
        "period": period,
        "periods": run,
        "period_age_days": statements.age_days(period),
        "statement_line": GROSS_PROFIT_ITEM,
    }

    if any(quarter not in statements.periods for quarter in run):
        return FieldReading(
            value=None,
            refusal=SignalIssue.FUNDAMENTAL_NOT_STORED,
            extras=extras,
        )
    series = [statements.income_line(quarter, GROSS_PROFIT_ITEM) for quarter in run]
    if any(figure is None for figure in series):
        return FieldReading(
            value=None,
            refusal=SignalIssue.STATEMENT_LINE_MISSING,
            extras=extras,
        )

    figures = [figure for figure in series if figure is not None]
    level = sum(figures) / len(figures)
    slope = _slope(figures)
    if level <= 0:
        # A four-quarter average gross profit of zero or less. Refused as a line
        # that cannot be read rather than divided by: the filings are real, and
        # a percentage of a negative average points the opposite way from the
        # business it claims to describe.
        return FieldReading(
            value=None,
            refusal=SignalIssue.STATEMENT_LINE_MISSING,
            extras={**extras, "average_level_vnd": level},
        )
    return FieldReading(
        value=100.0 * slope / level,
        extras={
            **extras,
            "average_level_vnd": level,
            "slope_vnd_per_quarter": slope,
        },
        degraded_reason=_staleness(statements, period),
    )


def _year_on_year(window: FieldWindow, item_id: str) -> FieldReading:
    """One line's change against the same quarter a year earlier, as a percent.

    Written once for the two fields that differ only in which line they read.
    What is shared is the refusal ladder, and it has to be shared: two results
    figures over one filing that refused under different codes for the same
    missing quarter would send a reader looking in two places for one gap.

    Three causes, three codes, each naming the input it could not find:

    * ``fundamental_not_stored`` — no income statement at or before this
      session, or none for the quarter a year back. The second half is the
      ordinary case for a recently listed company, and widening the window to
      cover it would answer a different question.
    * ``statement_line_missing`` — a statement stored for both quarters, and
      this line absent from one of them, or filed as a zero that the store
      cannot distinguish from an absence.
    * ``statement_line_missing`` again where the year-ago figure is negative.
      A percentage change against a loss is not orderable — a move from −100 to
      −50 is an improvement and reads as a fall of fifty percent — so the base
      is refused rather than signed over.
    """
    statements = window.quarterly
    if statements is None:
        return FieldReading(
            value=None,
            refusal=SignalIssue.FUNDAMENTAL_NOT_STORED,
            extras={"statement_line": item_id},
        )

    period = statements.newest
    prior = prior_year_period(period)
    extras: dict[str, object] = {
        "period": period,
        "prior_period": prior,
        "period_age_days": statements.age_days(period),
        "statement_line": item_id,
    }
    if prior not in statements.periods:
        return FieldReading(
            value=None,
            refusal=SignalIssue.FUNDAMENTAL_NOT_STORED,
            extras=extras,
        )

    current = statements.income_line(period, item_id)
    base = statements.income_line(prior, item_id)
    extras["current_figure"] = current
    extras["prior_year_figure"] = base
    if current is None or base is None or base < 0:
        return FieldReading(
            value=None,
            refusal=SignalIssue.STATEMENT_LINE_MISSING,
            extras=extras,
        )
    return FieldReading(
        value=100.0 * (current - base) / base,
        extras=extras,
        degraded_reason=_staleness(statements, period),
    )


def _slope(series: list[float]) -> float:
    """The least-squares slope of a short series against 0, 1, 2, ...

    Its own function so the trend reading reads as a trend rather than as
    arithmetic, and because the denominator is a constant for a fixed length:
    over four points it is 5, and spelling that out would hide what it is.
    """
    n = len(series)
    mean_x = (n - 1) / 2
    mean_y = sum(series) / n
    covariance = sum(
        (index - mean_x) * (value - mean_y) for index, value in enumerate(series)
    )
    variance = sum((index - mean_x) ** 2 for index in range(n))
    return covariance / variance


def _staleness(statements: QuarterlyStatements, period: str) -> SignalIssue | None:
    """Whether the newest quarter behind a figure is too old to narrate as now.

    The same bound the factor percentiles keep, and for the same reason: five
    months is past every Vietnamese filing deadline, so a figure older than that
    is a company that has missed a filing or a collector that has stopped. A
    degradation and never a refusal — the number was true of its quarter, and
    the quarter travels beside it.
    """
    if statements.age_days(period) > FUNDAMENTAL_STALE_DAYS:
        return SignalIssue.STALE_FUNDAMENTAL_PERIOD
    return None


__all__ = [
    "EARNINGS_LOOKBACK_SESSIONS",
    "EARNINGS_MIN_SESSIONS",
    "EPS_BASIC_ITEM",
    "GROSS_PROFIT_ITEM",
    "NET_PROFIT_ITEM",
    "QUARTERS_READ",
    "QuarterlyStatements",
    "TREND_KEYS",
    "TREND_QUARTERS",
    "YEAR_ON_YEAR_KEYS",
    "eps_basic_yoy_reading",
    "gross_profit_trend_reading",
    "net_profit_yoy_reading",
    "prior_year_period",
    "previous_period",
    "quarter_end",
    "quarterly_statements_for",
]
