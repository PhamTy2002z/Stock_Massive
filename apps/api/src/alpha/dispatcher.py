"""The one worker that drains the queue, and the backoff that keeps it honest.

A cohort is a table of ``pending`` runs and nothing else until something turns
them into Analyses. This is that something, and there is exactly one of it.

**One worker, and the claim is what makes that true.** A run is claimed by
``SELECT … FOR UPDATE SKIP LOCKED`` and flipped to ``producing`` inside the same
transaction, so a second worker started by accident skips the locked row, then
skips it again on the next pass because it is no longer ``pending``. Neither
guarantee is the last one: ``UNIQUE(symbol, trading_day)`` is, and it is a
constraint rather than a lock — a second producer that got all the way to a write
loses to the database.

**The order is total, and the fifth key is why.** On-demand with a user waiting,
then never-analysed symbols, then the oldest prior Analysis, then the symbols the
most Watchlists carry — and then the symbol itself, ascending. Without the last
one, two symbols equal on the first four drain in whatever order the planner felt
like, and a reproduction of last night's run is not a reproduction.

**The backoff lives in Postgres.** ``analysis_run.next_attempt_at`` is the whole
schedule: immediately after readiness, then +5 minutes, then +30, inside A2's
three-attempt ceiling. A restart before the deadline reads the schedule back out
of the store rather than losing it with an in-memory job status.

**``auth_unavailable`` is route-wide and is expressed as a schedule.** A
credential the route rejects has nothing to do with any symbol, so recording it
once per symbol would burn all three attempts for a hundred of them against one
condition — and would leave the whole cohort locked out until the next session.
Instead the run is put back to ``pending`` and *every* run waiting on that Trading
Day is pushed out fifteen minutes. The pause is therefore in Postgres, needs no
table, and survives a restart, which an in-process flag would not.

**An in-flight provider call is never preempted.** Shutdown is checked between
runs and never during one: the producer is synchronous and its generation is
already reserved and possibly already dispatched, so cancelling it would abandon
spend that has been committed and might have been charged.

**The 07:00 ICT deadline is a reporting boundary, not a licence.** Nothing here
relabels: a run is always produced for the Trading Day its row names. A cohort
that misses the window is read by ``cohort_state`` as ``partial`` or ``blocked``,
which is the honest answer and the only one available — an Analysis dated to the
previous Trading Day is the thing the deadline exists to forbid.

A2's stuck-run sweep keeps running beside this and stays the thing that clears a
run abandoned mid-production. This module deliberately grows no version of it: a
second thing writing ``failed`` over ``producing`` rows would race the first, and
the two would disagree about the window.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from src.stocks.trading_day import latest_trading_day

from .analysis_run import (
    MAX_ATTEMPTS_PER_SESSION,
    RunStatus,
    mark_run_failed,
    mark_run_ready,
    published_analysis,
    write_analysis,
)
from .models import Analysis, AnalysisRun, WatchlistEntry
from .producer import Producer, ProductionFailure

logger = logging.getLogger(__name__)

# How long a failed attempt waits before the next one, indexed by the attempt
# that just failed.
#
# The spec's schedule is "immediately after readiness, then +5 minutes, then +30"
# and it describes three attempts, not four: the *first* attempt is the immediate
# one — readiness is what gated it, and a run with no ``next_attempt_at`` is due
# now, which is what a freshly captured cohort looks like. So only the two gaps
# between the three attempts are written down here, and A2's ceiling is what ends
# the sequence rather than a third entry nothing could reach.
BACKOFF_MINUTES = (5, 30)

# What the dispatcher waits before touching the route again after it refused a
# credential. Fifteen minutes because the repair is a person rotating a key, not
# a transient the route recovers from on its own (``docs/adr/0014``).
AUTH_PROBE_MINUTES = 15

# The statuses a run has to be in to be worth claiming. `producing` is absent on
# purpose: a run in flight belongs to whoever claimed it, and a run stuck there
# is the A2 sweep's business rather than this module's.
CLAIMABLE = (RunStatus.PENDING.value, RunStatus.FAILED.value)


@dataclass(frozen=True)
class DrainReport:
    """What one pass of the dispatcher did, in the terms an operator reads.

    ``paused_until`` is set only where the route refused a credential, and it is
    the one outcome that says something about the system rather than about the
    symbols: every other field counts work.
    """

    trading_day: date | None
    produced: tuple[str, ...] = ()
    repaired: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    paused_until: datetime | None = None

    @property
    def claimed(self) -> int:
        return len(self.produced) + len(self.repaired) + len(self.failed)

    def as_result(self) -> dict:
        return {
            "trading_day": (
                None if self.trading_day is None else self.trading_day.isoformat()
            ),
            "claimed": self.claimed,
            "produced": list(self.produced),
            "repaired": list(self.repaired),
            "failed": list(self.failed),
            "paused_until": (
                None if self.paused_until is None else self.paused_until.isoformat()
            ),
        }


@dataclass
class _Tally:
    produced: list[str] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def claim_next_run(
    session: Session,
    trading_day: date,
    *,
    now: datetime | None = None,
) -> AnalysisRun | None:
    """Take the next run this worker should produce, or None when there is none.

    The claim is one statement and one commit: the row is locked with
    ``FOR UPDATE SKIP LOCKED``, flipped to ``producing`` and its attempt counted,
    and the transaction closes. A worker that dies immediately afterwards leaves
    exactly what a crash mid-production leaves — a ``producing`` run with its
    attempt spent, which is the sweep's to clear and honest about what happened.

    **Every origin is claimable, not only ``nightly`` and ``on_demand``.** The
    two named in the spec are the two that *create* queue entries; a run left
    ``failed`` by an inline retry is still work outstanding for that Trading Day,
    and filtering it out would strand that symbol until the next session with
    nothing saying why. This is the same reading ``cohort_state`` takes when it
    counts every origin.

    The ordering keys are the spec's five, in order, and the last is what makes
    the order total.
    """
    now = now or _now()

    # The most recent Analysis this symbol has, of any Trading Day. NULL means it
    # has never been analysed at all, which is a different fact from "analysed
    # long ago" and sorts ahead of every date.
    prior_analysis = (
        select(func.max(Analysis.trading_day))
        .where(Analysis.symbol == AnalysisRun.symbol)
        .correlate(AnalysisRun)
        .scalar_subquery()
    )
    # How many Watchlists carry this symbol. A tie-break rather than a priority:
    # by the time it is reached, two symbols are equal on urgency, novelty and
    # staleness, and the one more people are waiting on goes first.
    watchers = (
        select(func.count())
        .select_from(WatchlistEntry)
        .where(WatchlistEntry.symbol == AnalysisRun.symbol)
        .correlate(AnalysisRun)
        .scalar_subquery()
    )
    # A person is on the other end of an on-demand run and is looking at a
    # spinner. Nothing else in the queue has anybody waiting on it tonight.
    waiting = case(
        (AnalysisRun.requested_by_user_id.is_not(None), 1),
        else_=0,
    )

    run = session.execute(
        select(AnalysisRun)
        .where(
            AnalysisRun.trading_day == trading_day,
            AnalysisRun.status.in_(CLAIMABLE),
            AnalysisRun.attempts < MAX_ATTEMPTS_PER_SESSION,
            # The backoff, and the route-wide pause with it. A run with no
            # scheduled time is due now — that is what a fresh cohort looks like.
            (AnalysisRun.next_attempt_at.is_(None))
            | (AnalysisRun.next_attempt_at <= now),
        )
        .order_by(
            waiting.desc(),
            prior_analysis.asc().nullsfirst(),
            watchers.desc(),
            AnalysisRun.symbol.asc(),
        )
        .limit(1)
        .with_for_update(skip_locked=True, of=AnalysisRun)
    ).scalar_one_or_none()

    if run is None:
        return None

    run.status = RunStatus.PRODUCING.value
    run.attempts = (run.attempts or 0) + 1
    run.started_at = now
    run.finished_at = None
    run.error_code = None
    run.error_message = None
    run.next_attempt_at = None
    session.commit()
    return run


def drain_queue(
    session: Session,
    producer: Producer,
    *,
    trading_day: date | None = None,
    now: datetime | None = None,
    limit: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> DrainReport:
    """Produce every claimable run for one Trading Day, in the fixed order.

    ``should_stop`` is checked **between** runs and never during one. That is the
    no-preemption guarantee in its entirety: a generation that has been admitted
    has already had its worst case charged, so abandoning it mid-flight would
    spend money for nothing and leave a ``producing`` row for the sweep.

    ``limit`` bounds one pass rather than the evening. It exists so a scheduled
    tick cannot run for hours on a large cohort and so a test can drain one run
    at a time; the next tick picks the queue up where this one left it, because
    the queue is the table.
    """
    now = now or _now()
    trading_day = trading_day or latest_trading_day(session)
    if trading_day is None:
        # Nothing has ever been collected, so there is no Trading Day to produce
        # for. Manufacturing one from an earlier session is what the availability
        # deadline forbids, so this reports nothing rather than reaching back.
        return DrainReport(trading_day=None)

    tally = _Tally()
    while True:
        if limit is not None and _claimed(tally) >= limit:
            break
        if should_stop is not None and should_stop():
            logger.info("Stopping the Analysis dispatcher between runs")
            break

        run = claim_next_run(session, trading_day, now=now)
        if run is None:
            break

        paused = _produce_claimed(session, run, producer, tally, now=now)
        if paused is not None:
            return DrainReport(
                trading_day=trading_day,
                produced=tuple(tally.produced),
                repaired=tuple(tally.repaired),
                failed=tuple(tally.failed),
                paused_until=paused,
            )

    return DrainReport(
        trading_day=trading_day,
        produced=tuple(tally.produced),
        repaired=tuple(tally.repaired),
        failed=tuple(tally.failed),
    )


def _claimed(tally: _Tally) -> int:
    return len(tally.produced) + len(tally.repaired) + len(tally.failed)


def _produce_claimed(
    session: Session,
    run: AnalysisRun,
    producer: Producer,
    tally: _Tally,
    *,
    now: datetime,
) -> datetime | None:
    """Produce one claimed run. Returns the pause deadline, or None.

    The two writes are A2's and in A2's order: the Analysis is committed first
    and the run flipped ``ready`` second, so a death between them leaves a
    ``producing`` run whose Analysis already exists — which the branch above
    repairs without producing again.
    """
    symbol = run.symbol

    published = published_analysis(session, symbol, run.trading_day)
    if published is not None:
        # An Analysis already exists for the pair: a death between the two
        # writes, or a concurrent producer that won. Nothing to generate, and the
        # only thing wrong is the run's status.
        mark_run_ready(session, run)
        tally.repaired.append(symbol)
        return None

    try:
        draft = producer(symbol, run.trading_day)
    except ProductionFailure as failure:
        if failure.code == "auth_unavailable":
            return _pause_route(session, run, now=now, reason=failure.message)
        mark_run_failed(session, run, failure.code, failure.message)
        _schedule_retry(session, run, now=now)
        tally.failed.append(symbol)
        return None

    write_analysis(session, symbol, run.trading_day, draft)
    mark_run_ready(session, run)
    tally.produced.append(symbol)
    return None


def _schedule_retry(session: Session, run: AnalysisRun, *, now: datetime) -> None:
    """Put the next attempt on the clock, or leave the run finished.

    Indexed by attempts already spent, so the schedule is a property of the row
    rather than of whoever is reading it — which is what lets a restart resume it.
    A run at the ceiling gets no time at all: there is no fourth attempt to
    schedule, and a date in that column would say there was.
    """
    if run.attempts >= MAX_ATTEMPTS_PER_SESSION:
        run.next_attempt_at = None
        session.commit()
        return

    # `attempts` is the attempt that just failed, and the gaps are indexed from
    # it: the first failure waits five minutes, the second thirty. Clamped rather
    # than indexed blindly so a raised ceiling widens the sequence instead of
    # raising IndexError on the first symbol of the evening.
    minutes = BACKOFF_MINUTES[min(run.attempts, len(BACKOFF_MINUTES)) - 1]
    run.next_attempt_at = now + timedelta(minutes=minutes)
    session.commit()


def _pause_route(
    session: Session,
    run: AnalysisRun,
    *,
    now: datetime,
    reason: str,
) -> datetime:
    """Push the whole Trading Day out, and put this run back where it was.

    The claimed run returns to ``pending`` rather than being recorded ``failed``:
    the route refused a credential, which says nothing about this symbol, and a
    failure written here is a failure a reader would go looking for in the data.

    **The attempt it spent is not refunded.** ``attempts`` counts attempts that
    ran, and an attempt that reached the route and was turned away did run — a
    reservation may already have been committed against it. Refunding would make
    the column mean "attempts that failed for a reason we consider the symbol's",
    which is not a thing the ceiling can be reasoned about with.

    Every other waiting run for the day is pushed out with it, and that push
    **never pulls a later schedule forward**: a run already backing off for
    thirty minutes keeps its thirty.
    """
    until = now + timedelta(minutes=AUTH_PROBE_MINUTES)

    run.status = RunStatus.PENDING.value
    run.finished_at = None
    run.error_code = None
    run.error_message = None
    run.next_attempt_at = until
    session.commit()

    paused = session.execute(
        update(AnalysisRun)
        .where(
            AnalysisRun.trading_day == run.trading_day,
            AnalysisRun.status.in_(CLAIMABLE),
            AnalysisRun.id != run.id,
            (AnalysisRun.next_attempt_at.is_(None))
            | (AnalysisRun.next_attempt_at < until),
        )
        .values(next_attempt_at=until)
    ).rowcount
    session.commit()

    logger.warning(
        "The LLM route refused a credential (%s); the Analysis dispatcher is "
        "paused until %s and %d other run(s) were pushed with it",
        reason,
        until.isoformat(),
        paused,
    )
    return until


__all__ = [
    "AUTH_PROBE_MINUTES",
    "BACKOFF_MINUTES",
    "CLAIMABLE",
    "DrainReport",
    "claim_next_run",
    "drain_queue",
]
