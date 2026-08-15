"""The evening's cohort: who is in it, when it is captured, and how it is going.

Two facts shape everything here.

**The cohort is captured by data, not by a clock.** The moment the first Market
Snapshot establishes a new data-defined **Trading Day**, the distinct union of
every **Watchlist** becomes that evening's cohort — one `pending` **Analysis
Run** per symbol, origin `nightly`. A clock cannot do this job: the Main Source
appends the session that just closed hours after the close, so 16:15 routinely
comes away with yesterday's session, and a cohort captured on the hour would be
a cohort for a Trading Day that does not exist yet.

**The cohort has no table.** Its state is *derived* from the ``analysis_run``
rows for that Trading Day, which already carry status, origin and attempts. A
cohort table would be a second source of truth for a fact the runs already
state, and the two would disagree the first time a run was retried by hand. No
Alembic revision is added by this module and none is wanted.

Three consequences worth stating, because each is a thing somebody will
reasonably expect to be false:

*Removing a symbol after capture does not cancel its run.* An Analysis is keyed
by ``(symbol, trading_day)`` and shared between everyone watching it, so it was
never that user's to cancel. Nothing here reads the Watchlist again after the
capture.

*Capturing twice captures nothing.* A second Market Snapshot for the same day
finds every run already there. The idempotency is
``UNIQUE(symbol, trading_day)``, not a flag this module keeps.

*A symbol added after capture is not this module's business.* It takes the
on-demand lane (``src/alpha/on_demand.py``), which deduplicates on the same key
and costs the user nothing when a run already exists.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.stocks.trading_day import latest_trading_day
from src.stocks.universe import build_universe

from .analysis_run import RunOrigin, RunStatus
from .models import AnalysisRun, WatchlistEntry

logger = logging.getLogger(__name__)

# When an Analysis for a Trading Day has to be readable. Nothing in this module
# may meet it by relabelling: a cohort is captured for the day the store
# actually established, and the previous Trading Day is never dressed up as this
# one to make the window (``docs/adr/0014``, spec 0003 §11).
AVAILABILITY_DEADLINE_HOUR_ICT = 7


class CohortState(str, Enum):
    """How one evening's cohort is going, derived from its runs.

    ``blocked`` is the honest answer where there is nothing to run against at
    all — no new Trading Day was established, so the cohort has no session to be
    about. It is deliberately not ``failed``: nothing was attempted, and saying
    a cohort failed when the market never closed a session anybody collected
    would send an operator looking in the wrong place.
    """

    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CohortCapture:
    """What capturing one evening's cohort did.

    ``created`` and ``joined`` are separate because the second one is the normal
    steady state rather than a problem: a second Snapshot for the same day, a
    restart, or a symbol somebody already asked for on demand all arrive here as
    a run that exists, and only the first of those is a repeat capture.
    """

    trading_day: date | None
    created: tuple[str, ...] = ()
    joined: tuple[str, ...] = ()

    @property
    def captured(self) -> bool:
        return bool(self.created)

    def as_result(self) -> dict:
        return {
            "trading_day": None if self.trading_day is None else self.trading_day.isoformat(),
            "created": list(self.created),
            "joined": list(self.joined),
        }


@dataclass(frozen=True)
class CohortStatus:
    """One evening's cohort as an operator reads it.

    The counts travel with the state because the state alone cannot be acted on:
    ``partial`` over one failed symbol and ``partial`` over forty are the same
    word and very different evenings.
    """

    trading_day: date | None
    state: CohortState
    pending: int = 0
    producing: int = 0
    ready: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.pending + self.producing + self.ready + self.failed

    def as_result(self) -> dict:
        return {
            "trading_day": None if self.trading_day is None else self.trading_day.isoformat(),
            "state": self.state.value,
            "total": self.total,
            "pending": self.pending,
            "producing": self.producing,
            "ready": self.ready,
            "failed": self.failed,
        }


def watchlist_union(session: Session) -> tuple[str, ...]:
    """Every symbol anybody watches, once each, alphabetically.

    The **Universe** is applied here rather than left to the producer, because a
    symbol that has left it is ``unsupported`` and produces nothing at all —
    queueing it would mint a run for a pair that can only ever fail, and the rail
    already tells that user why their symbol went quiet.

    Alphabetical so an interrupted capture resumes in the order it started, and
    so two readings of the same store cannot disagree about the cohort's shape.
    """
    watched = session.execute(
        select(distinct(WatchlistEntry.symbol)).order_by(WatchlistEntry.symbol.asc())
    ).scalars()
    universe = build_universe(session)
    return tuple(symbol for symbol in watched if universe.contains(symbol))


def capture_nightly_cohort(
    session: Session,
    trading_day: date | None = None,
    symbols: Sequence[str] | None = None,
) -> CohortCapture:
    """Queue one `pending` run per watched symbol for this Trading Day.

    Idempotent by ``UNIQUE(symbol, trading_day)`` rather than by a flag: a second
    Market Snapshot for the same day, a restart mid-capture and a concurrent
    capture all end with exactly one run per pair, and none of them needs this
    module to remember anything.

    Committed per symbol rather than in one transaction. A capture interrupted
    halfway leaves the symbols it reached queued and the rest to be picked up by
    the next call — which is what a restart is, and what makes resuming free.

    ``trading_day`` defaults to the newest one the store holds. ``None`` there
    means no session has ever been collected, and nothing is captured: a cohort
    for a Trading Day that does not exist is the manufactured Analysis the
    availability deadline forbids.
    """
    trading_day = trading_day or latest_trading_day(session)
    if trading_day is None:
        logger.info("No Trading Day is established, so no cohort was captured")
        return CohortCapture(trading_day=None)

    wanted = tuple(symbols) if symbols is not None else watchlist_union(session)
    if not wanted:
        return CohortCapture(trading_day=trading_day)

    existing = set(
        session.execute(
            select(AnalysisRun.symbol).where(AnalysisRun.trading_day == trading_day)
        ).scalars()
    )

    created: list[str] = []
    joined: list[str] = [symbol for symbol in wanted if symbol in existing]
    for symbol in wanted:
        if symbol in existing:
            continue
        session.add(
            AnalysisRun(
                symbol=symbol,
                trading_day=trading_day,
                status=RunStatus.PENDING.value,
                origin=RunOrigin.NIGHTLY.value,
                attempts=0,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            # Somebody else queued this pair between the read and the write —
            # the on-demand lane, or a second capture. Theirs is as good as
            # ours: the row identifies the pair, not who asked for it.
            session.rollback()
            joined.append(symbol)
            continue
        created.append(symbol)

    if created:
        logger.info(
            "Captured the nightly cohort for %s: %d new run(s), %d already queued",
            trading_day,
            len(created),
            len(joined),
        )
    return CohortCapture(
        trading_day=trading_day,
        created=tuple(created),
        joined=tuple(sorted(joined)),
    )


def cohort_state(session: Session, trading_day: date | None = None) -> CohortStatus:
    """How this evening's cohort is going, read off the runs and nothing else.

    Every origin counts, not only ``nightly``. The four states describe the
    work outstanding for one Trading Day, and a symbol somebody added at 20:00
    is work outstanding for that Trading Day — reported per origin, a cohort
    would read ``complete`` while the queue still had rows in it.

    ``blocked`` covers both ways there is nothing to be run: no Trading Day was
    established at all, and a Trading Day nobody watches a symbol for. Neither is
    a failure, and both are answered the same way — there is no cohort here.
    """
    trading_day = trading_day or latest_trading_day(session)
    if trading_day is None:
        return CohortStatus(trading_day=None, state=CohortState.BLOCKED)

    counts = dict(
        session.execute(
            select(AnalysisRun.status, func.count())
            .where(AnalysisRun.trading_day == trading_day)
            .group_by(AnalysisRun.status)
        ).all()
    )
    status = CohortStatus(
        trading_day=trading_day,
        state=CohortState.BLOCKED,
        pending=int(counts.get(RunStatus.PENDING.value, 0)),
        producing=int(counts.get(RunStatus.PRODUCING.value, 0)),
        ready=int(counts.get(RunStatus.READY.value, 0)),
        failed=int(counts.get(RunStatus.FAILED.value, 0)),
    )
    if status.total == 0:
        return status
    return CohortStatus(
        trading_day=status.trading_day,
        state=_state_of(status),
        pending=status.pending,
        producing=status.producing,
        ready=status.ready,
        failed=status.failed,
    )


def _state_of(status: CohortStatus) -> CohortState:
    """The three states a cohort with runs in it can be in.

    ``partial`` covers every finished evening that lost a symbol, including the
    one that lost all of them. There is no fifth state for *all failed*: the four
    are what the interface renders, and an evening where nothing succeeded is
    read the same way as one where two symbols did — go and look at the runs.
    """
    if status.pending or status.producing:
        return CohortState.RUNNING
    if status.failed:
        return CohortState.PARTIAL
    return CohortState.COMPLETE


__all__ = [
    "AVAILABILITY_DEADLINE_HOUR_ICT",
    "CohortCapture",
    "CohortState",
    "CohortStatus",
    "capture_nightly_cohort",
    "cohort_state",
    "watchlist_union",
]
