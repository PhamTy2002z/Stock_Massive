"""Filling the daily spine, one symbol at a time, resumably and without a ledger.

**There is no checkpoint table.** Progress is derived from the store: a symbol
that already holds the requested depth and reaches the newest session the spine
has is skipped. The write is an idempotent upsert, so a run interrupted anywhere
resumes for free — and there is no second record of progress that can disagree
with the rows sitting next to it. A checkpoint table would have to be kept true
against the very thing it describes.

**The skip reference comes from the calendar, never from this table.**
Both obvious in-store references are this job's own output, and both make the
spine a fixed point. ``trading_day.latest_trading_day`` reads this very table.
So does ``max(trading_day)`` within the series, which was the reference here
until it was measured: every symbol that reached the newest stored session is
"current" *with that session*, so a spine that missed a day could never be told
to go and get it. VNINDEX showed it sharpest — the only symbol in its series,
compared against itself, skipped on every run once it reached its depth, with
the store frozen three days behind the market. The reference is
:func:`latest_expected_session` instead: the newest weekday, by the clock.

**One symbol failing does not end the run.** Market scope is 1,523 network
calls against a provider with no SLA; a run that stopped on the first timeout
would never finish, and there is nothing to lose by continuing — the failed
symbol is simply not deep enough next time. Each symbol gets its own session and
its own commit for the same reason: an aborted transaction must cost one symbol,
not the run's whole progress.

Scopes:

- ``declared`` — the 30 symbols the Universe declares, 2,000 sessions (~8 years,
  one call each at the provider's row cap).
- ``index`` — VNINDEX as the ``index`` series, 2,000 sessions.
- ``market`` — every share the listing register lists, 400 sessions: 52 weeks
  plus the buffer a relative-return screener needs at the edges.
"""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.database import get_sync_db
from src.core.quota import QuotaLane, quota_lane
from src.stocks.models import BarDaily
from src.stocks.providers import vnstock_daily
from src.stocks.providers.vnstock_daily import SERIES_EQUITY, SERIES_INDEX
from src.stocks.trading_day import spine_freshness
from src.stocks.universe import build_universe

logger = logging.getLogger(__name__)

SCOPE_DECLARED = "declared"
SCOPE_MARKET = "market"
SCOPE_INDEX = "index"
SCOPES = (SCOPE_DECLARED, SCOPE_MARKET, SCOPE_INDEX)

#: The index this market is quoted against. One symbol, its own series.
INDEX_SYMBOL = "VNINDEX"

#: Depth per scope. Declared symbols carry the studies that need years of
#: history; the market half only has to answer 52-week questions.
DEFAULT_SESSIONS = {
    SCOPE_DECLARED: 2000,
    SCOPE_INDEX: 2000,
    SCOPE_MARKET: 400,
}

SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class SymbolReport:
    """One symbol's line in the run log."""

    symbol: str
    series: str
    skipped: bool = False
    rows_written: int = 0
    sessions_stored: int = 0
    calls: int = 0
    error: str | None = None


@dataclass
class BackfillReport:
    """What one run did, in terms the operator asked about."""

    scope: str
    sessions: int
    symbols: list[SymbolReport] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return sum(1 for report in self.symbols if not report.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for report in self.symbols if report.skipped)

    @property
    def rows_written(self) -> int:
        return sum(report.rows_written for report in self.symbols)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(
            report.symbol for report in self.symbols if report.error is not None
        )


def scope_symbols(
    session: Session, scope: str
) -> tuple[tuple[str, str], ...]:
    """The ``(symbol, series)`` pairs a scope covers, in a stable order.

    Stable so an interrupted run walks the market the same way next time, which
    is what makes "already deep enough" a resumable answer rather than a guess
    about which symbols were reached.
    """
    if scope == SCOPE_DECLARED:
        return tuple(
            (symbol, SERIES_EQUITY) for symbol in build_universe(session).symbols
        )
    if scope == SCOPE_INDEX:
        return ((INDEX_SYMBOL, SERIES_INDEX),)
    if scope == SCOPE_MARKET:
        universe = build_universe(session, with_market=True)
        return tuple((symbol, SERIES_EQUITY) for symbol in universe.market)
    raise ValueError(f"{scope!r} is not a scope; expected one of {SCOPES}")


#: The market's clock. A session is dated by the day it traded in Vietnam, so
#: the calendar this job compares against has to be read there too.
ICT = ZoneInfo("Asia/Ho_Chi_Minh")


def latest_expected_session(today: date | None = None) -> date:
    """The day a session would carry if the market ran on the newest weekday.

    Weekday rather than trading day, and that is the whole point: a trading-day
    calendar is derived from the spine, so asking one would put this job back on
    data it is itself responsible for producing. A public holiday costs one call
    per symbol that comes back with nothing new, and the ``observed_at`` guard in
    :func:`is_deep_enough` holds it to one for the day.

    During trading hours this is today, so the run writes today's partial bar and
    then stands down until tomorrow — the old reference skipped the market
    outright in that window, which is the behaviour its own docstring set out to
    avoid.
    """
    day = today or datetime.now(ICT).date()
    while day.weekday() >= 5:  # Saturday, Sunday: no session carries these dates
        day -= timedelta(days=1)
    return day


def is_deep_enough(
    session: Session, symbol: str, *, sessions: int, reference: date | None
) -> bool:
    """Whether this symbol needs no call at all.

    Depth has to hold, and so does currency — depth alone would freeze a symbol
    at whatever day it was first filled on, and currency alone would leave a
    symbol that only ever got last week permanently shallow.

    Currency is **when it was last asked about**, not when it last traded. A
    thinly traded board is full of shares that go days without a matched
    session: measured 2026-08-27, 677 of 1,522 listed shares had no session that
    day, 303 of them none for over a week. Judged by their newest session those
    symbols can never be current, so every run would call the provider for all
    of them again and spend 44% of a market-wide pass re-answering "nothing has
    happened here". ``observed_at`` is the fact that actually settles it: asked
    on or after the market's newest session, the store already holds the
    provider's answer, whether or not that answer contained a new bar.
    """
    stored, last, asked = session.execute(
        select(
            func.count(BarDaily.trading_day),
            func.max(BarDaily.trading_day),
            func.max(BarDaily.observed_at),
        ).where(BarDaily.symbol == symbol)
    ).one()
    if int(stored or 0) < sessions:
        return False
    if reference is None:
        return False
    if last is not None and last >= reference:
        return True
    return asked is not None and asked.date() >= reference


def run(
    *,
    scope: str,
    sessions: int | None = None,
    session_factory: SessionFactory = get_sync_db,
    fetch: vnstock_daily.Fetch | None = None,
    today: date | None = None,
) -> BackfillReport:
    """Fill the spine for one scope and report what happened per symbol.

    ``session_factory``, ``fetch`` and ``today`` are injectable so the suite can
    prove the skip rule and the failure isolation without reaching the network;
    production passes none of them.
    """
    if scope not in SCOPES:
        raise ValueError(f"{scope!r} is not a scope; expected one of {SCOPES}")
    depth = sessions if sessions is not None else DEFAULT_SESSIONS[scope]
    report = BackfillReport(scope=scope, sessions=depth)

    with session_factory() as session:
        targets = scope_symbols(session, scope)
    if not targets:
        logger.warning(
            "Scope %s covers no symbols. For %s that means the listing register "
            "is empty — refresh it before asking for the market",
            scope,
            SCOPE_MARKET,
        )
        return report

    logger.info(
        "Daily spine backfill starting: scope=%s symbols=%d sessions=%d",
        scope,
        len(targets),
        depth,
    )
    # Declared once, here, because this is the entry point that knows the answer
    # — which is how the arbiter is meant to be used (``docs/adr/0014``): the
    # lane rides a ``ContextVar`` so the provider call underneath neither knows
    # nor needs to. ``BACKFILL`` is the right lane and not ``LEGACY``: it stands
    # aside whenever a caller with a user waiting is queued, and it accepts an
    # unbounded wait, which is what a batch job of 1,523 symbols should do and
    # what a request serving a person must not.
    with quota_lane(QuotaLane.BACKFILL):
        for symbol, series in targets:
            report.symbols.append(
                _one_symbol(
                    symbol,
                    series,
                    depth=depth,
                    session_factory=session_factory,
                    fetch=fetch,
                    today=today,
                )
            )

    logger.info(
        "Daily spine backfill done: scope=%s attempted=%d skipped=%d rows=%d "
        "failed=%d",
        scope,
        report.attempted,
        report.skipped,
        report.rows_written,
        len(report.failures),
    )
    return report


def _one_symbol(
    symbol: str,
    series: str,
    *,
    depth: int,
    session_factory: SessionFactory,
    fetch: vnstock_daily.Fetch | None,
    today: date | None,
) -> SymbolReport:
    """One symbol, in its own transaction, never raising into the run.

    The skip decision is taken inside the same session that would do the write,
    so a symbol filled by a concurrent run is seen as filled.
    """
    try:
        with session_factory() as session:
            reference = latest_expected_session(today)
            if is_deep_enough(session, symbol, sessions=depth, reference=reference):
                logger.info(
                    "%s skipped: already %d sessions deep and current",
                    symbol,
                    depth,
                )
                return SymbolReport(symbol=symbol, series=series, skipped=True)

            outcome = vnstock_daily.ensure_daily_bars(
                session,
                symbol,
                sessions=depth,
                series=series,
                fetch=fetch,
                today=today,
            )
        logger.info(
            "%s: rows_written=%d sessions_stored=%d calls=%d span=%s..%s",
            outcome.symbol,
            outcome.rows_written,
            outcome.sessions_stored,
            outcome.calls,
            outcome.first_session,
            outcome.last_session,
        )
        return SymbolReport(
            symbol=outcome.symbol,
            series=series,
            rows_written=outcome.rows_written,
            sessions_stored=outcome.sessions_stored,
            calls=outcome.calls,
        )
    except Exception as exc:  # noqa: BLE001 - one symbol must not end the run
        logger.warning("%s failed: %s", symbol, exc)
        return SymbolReport(symbol=symbol, series=series, error=str(exc))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.stocks.backfill_daily",
        description="Fill the market-wide daily price spine from the provider.",
    )
    parser.add_argument("--scope", required=True, choices=list(SCOPES))
    parser.add_argument(
        "--sessions",
        type=int,
        default=None,
        help="How many sessions deep to go; the scope's own default otherwise.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    args = _parse_args(argv)
    report = run(scope=args.scope, sessions=args.sessions)

    # Said out loud at the end of every run, because this is the one moment
    # somebody is looking. The Trading Day calendar is derived from this table,
    # so a spine nobody is feeding is not a stale table — it is a market whose
    # newest session stops moving while every answer still carries a date.
    with get_sync_db() as session:
        freshness = spine_freshness(session)
    logger.info("Daily spine: %s", freshness.describe())

    if report.failures:
        # A non-zero exit so an operator sees it, after every other symbol has
        # been written. Re-running the same command retries only what failed.
        logger.warning("Symbols that failed: %s", ", ".join(report.failures))
        return 1
    if freshness.is_empty or freshness.is_stale:
        logger.warning(
            "The daily spine is not current after a clean run: %s. Nothing "
            "downstream can serve a session it does not hold.",
            freshness.describe(),
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
