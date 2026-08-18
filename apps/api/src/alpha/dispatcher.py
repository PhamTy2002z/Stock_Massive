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
relabels: a run is always produced for the Trading Day its row names, and the
dispatcher keeps draining past the hour. What changes at 07:00 is only what the
evening is *called* — ``cohort_report`` reads an evening still carrying work as
``partial`` rather than ``running``. An Analysis dated to the previous Trading
Day is the thing the deadline exists to forbid, so it is the one thing that is
never done to meet it.

A2's stuck-run sweep keeps running beside this and stays the thing that clears a
run abandoned mid-production. This module deliberately grows no version of it: a
second thing writing ``failed`` over ``producing`` rows would race the first, and
the two would disagree about the window.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from src.stocks.providers.normalize import VN_TZ
from src.stocks.trading_day import latest_trading_day

from .analysis_run import (
    AVAILABILITY_DEADLINE_HOUR_ICT,
    MAX_ATTEMPTS_PER_SESSION,
    SNAPSHOT_WAIT_MINUTES,
    RunStatus,
    availability_deadline,
    defer_run,
    mark_run_failed,
    mark_run_ready,
    published_analysis,
    still_waiting_for_data,
    write_analysis,
)
from .models import Analysis, AnalysisRun, WatchlistEntry
from .nightly import CohortState, CohortStatus, cohort_state
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

# The 07:00 ICT deadline is defined in `analysis_run`, because that is the
# module that has to stop waiting on it, and re-exported through this one's
# `__all__` because this is the module that measures against it. It changes no
# behaviour at all — nothing is skipped, nothing is relabelled, and a run
# claimed at 07:01 is produced exactly as one claimed at 23:00 — it only changes
# what an evening is *called* once it is missed (``docs/adr/0014``, spec 0003
# §11).


@dataclass
class DrainReport:
    """What one pass of the dispatcher did, in the terms an operator reads.

    Mutable, and it is the pass's running tally rather than a summary built at
    the end. One type instead of two: a tally and a report holding the same four
    lists would be the same fact in two shapes, and the second would exist only
    to be copied from the first.

    ``deferred`` is the lane that produced nothing and failed nothing: the
    symbol's session had not been collected yet and the run went back on the
    queue with its attempt refunded. Counted apart from ``failed`` because an
    operator reading a hundred failures goes looking for a defect, and a hundred
    deferrals mean the Collector is simply still working.

    ``paused_until`` is set only where the route refused a credential, and it is
    the one outcome that says something about the system rather than about the
    symbols: every other field counts work.
    """

    trading_day: date | None
    produced: list[str] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    paused_until: datetime | None = None

    @property
    def claimed(self) -> int:
        return (
            len(self.produced)
            + len(self.repaired)
            + len(self.failed)
            + len(self.deferred)
        )

    def as_result(self) -> dict:
        return {
            "trading_day": (
                None if self.trading_day is None else self.trading_day.isoformat()
            ),
            "claimed": self.claimed,
            "produced": list(self.produced),
            "repaired": list(self.repaired),
            "failed": list(self.failed),
            "deferred": list(self.deferred),
            "paused_until": (
                None if self.paused_until is None else self.paused_until.isoformat()
            ),
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cohort_report(
    session: Session,
    trading_day: date | None = None,
    *,
    now: datetime | None = None,
) -> CohortStatus:
    """The evening's cohort as an operator reads it, deadline included.

    ``cohort_state`` answers what the runs say; this answers what they say *at a
    time*. Past 07:00 ICT an evening still carrying pending or producing runs is
    no longer ``running`` — it is a cohort that missed its window, and the honest
    word for it is ``partial``: some of it may be published, and the rest will not
    arrive when it was promised.

    **Nothing is relabelled to meet the deadline.** This is a reporting boundary
    and not a licence: the runs keep their Trading Day, the dispatcher keeps
    draining them, and an Analysis is never dated to the previous session to make
    the window (``docs/adr/0014``).

    ``blocked`` stays what ``cohort_state`` means by it — no Trading Day was
    established at all — and is not reused here for an evening that ran late.

    **``partial`` now covers two evenings an operator acts on differently**, and
    the counts are what separate them, not the word:

    - ``pending + producing == 0`` — the queue is drained and some symbols
      failed. Go and read their error codes.
    - ``pending + producing > 0`` — it is past 07:00 and the queue is still
      grinding. Go and look at the dispatcher.

    The four states are fixed by spec 0003 §11 and a late evening has to map onto
    one of them, so the state word is deliberately coarse — the same choice
    ``cohort_state`` makes when an evening nobody watches a symbol for reports
    ``complete`` with ``total: 0``. **Anything rendering ``partial`` shows the
    counts beside it**; the word alone cannot be acted on.
    """
    status = cohort_state(session, trading_day)
    if status.state is not CohortState.RUNNING or status.trading_day is None:
        return status
    now = now or _now()
    if now < availability_deadline(status.trading_day):
        return status

    logger.warning(
        "The cohort for %s is past the %02d:00 ICT availability deadline with "
        "%d run(s) outstanding",
        status.trading_day,
        AVAILABILITY_DEADLINE_HOUR_ICT,
        status.pending + status.producing,
    )
    return replace(status, state=CohortState.PARTIAL)


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
    clock: Callable[[], datetime] = _now,
    limit: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> DrainReport:
    """Produce every claimable run for one Trading Day, in the fixed order.

    **A clock rather than an instant.** One pass makes as many LLM calls as the
    queue has work, so a pass takes minutes; a single ``now`` read at the top
    would schedule a failure late in the pass five minutes from when the pass
    *started*, which can already be in the past by the time it is written. Each
    claim and each schedule reads the time again.

    ``should_stop`` is checked **between** runs and never during one. That is the
    no-preemption guarantee in its entirety: a generation that has been admitted
    has already had its worst case charged, so abandoning it mid-flight would
    spend money for nothing and leave a ``producing`` row for the sweep.

    ``limit`` bounds one pass rather than the evening. It exists so a scheduled
    tick cannot run for hours on a large cohort and so a test can drain one run
    at a time; the next tick picks the queue up where this one left it, because
    the queue is the table.
    """
    trading_day = trading_day or latest_trading_day(session)
    if trading_day is None:
        # Nothing has ever been collected, so there is no Trading Day to produce
        # for. Manufacturing one from an earlier session is what the availability
        # deadline forbids, so this reports nothing rather than reaching back.
        return DrainReport(trading_day=None)

    report = DrainReport(trading_day=trading_day)
    while True:
        if limit is not None and report.claimed >= limit:
            break
        if should_stop is not None and should_stop():
            logger.info("Stopping the Analysis dispatcher between runs")
            break

        run = claim_next_run(session, trading_day, now=clock())
        if run is None:
            break

        report.paused_until = _produce_claimed(
            session, run, producer, report, clock=clock
        )
        if report.paused_until is not None:
            break

    return report


def _produce_claimed(
    session: Session,
    run: AnalysisRun,
    producer: Producer,
    report: DrainReport,
    *,
    clock: Callable[[], datetime],
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
        report.repaired.append(symbol)
        return None

    try:
        draft = producer(symbol, run.trading_day)
    except ProductionFailure as failure:
        # The time is read *after* the generation, not before it: what the
        # backoff is measured from is the moment this attempt gave up, and a
        # generation can take a minute or two of that gap on its own.
        now = clock()
        if failure.code == "auth_unavailable":
            return _pause_route(session, run, now=now, reason=failure.message)
        if still_waiting_for_data(failure, run.trading_day, now):
            # The Collector has not reached this symbol for this session yet.
            # Deferred rather than failed, and the attempt refunded — see
            # `defer_run`. Only this run waits: unlike a refused credential, a
            # session nobody collected says something about one symbol, and the
            # symbol behind it in the queue may well have been collected.
            defer_run(
                session,
                run,
                failure.code,
                failure.message,
                until=now + timedelta(minutes=SNAPSHOT_WAIT_MINUTES),
            )
            report.deferred.append(symbol)
            return None
        mark_run_failed(session, run, failure.code, failure.message)
        _schedule_retry(session, run, now=now)
        report.failed.append(symbol)
        return None

    write_analysis(session, symbol, run.trading_day, draft)
    mark_run_ready(session, run)
    report.produced.append(symbol)
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

    **The attempt is refunded, and it has to be.** ADR-0014 says to mark the
    current run *retryable*, and the ordering this dispatcher applies is total and
    deterministic — so every fifteen-minute probe re-claims the same
    top-priority run. Counting those attempts would lock that symbol out after
    three probes, then start on the next one: the spec's "burn all three attempts
    for a hundred symbols" would be serialized rather than prevented. The ceiling
    exists to stop a pair being retried into the ground for its own reasons, and
    a credential the route rejected is not one of them.

    Every other waiting run for the day is pushed out with it, and that push
    **never pulls a later schedule forward**: a run already backing off for
    thirty minutes keeps its thirty.
    """
    until = now + timedelta(minutes=AUTH_PROBE_MINUTES)

    run.status = RunStatus.PENDING.value
    run.attempts = max((run.attempts or 1) - 1, 0)
    run.started_at = None
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
    "AVAILABILITY_DEADLINE_HOUR_ICT",
    "BACKOFF_MINUTES",
    "CLAIMABLE",
    "DrainReport",
    "availability_deadline",
    "claim_next_run",
    "cohort_report",
    "drain_queue",
]
