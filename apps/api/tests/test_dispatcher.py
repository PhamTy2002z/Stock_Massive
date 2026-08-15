"""Who drains the queue, in what order, and what happens when it cannot.

Four things carry this module, and every test here is one of them —

*One worker.* The claim is ``FOR UPDATE SKIP LOCKED`` plus a flip to
``producing`` in the same transaction, so a second worker skips the locked row
and then skips it again because it is no longer claimable. The last barrier is
``UNIQUE(symbol, trading_day)``, which is a constraint rather than a lock.

*The order is total.* Five keys, in order, and the fifth exists so two symbols
equal on the first four cannot drain in whatever order the planner felt like —
a reproduction of last night's run has to be a reproduction.

*The backoff is in Postgres.* ``next_attempt_at`` is the whole schedule, so a
restart reads it back rather than losing it with an in-memory job status.

*``auth_unavailable`` is route-wide.* One condition, not one failure per symbol,
and expressed as a schedule so it needs no table and survives a restart.

Run against a live Postgres. ``SKIP LOCKED`` and ``NULLS FIRST`` are what is
under test, and SQLite has neither.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from src.alpha.analysis_run import (
    MAX_ATTEMPTS_PER_SESSION,
    RunOrigin,
    RunStatus,
    stored_run,
)
from src.alpha.dispatcher import (
    AUTH_PROBE_MINUTES,
    BACKOFF_MINUTES,
    claim_next_run,
    drain_queue,
)
from src.alpha.jobs import drain_analysis_queue
from src.alpha.models import Analysis, AnalysisRun, WatchlistEntry
from src.alpha.nightly import CohortState, cohort_state
from src.alpha.producer import AnalysisDraft, ProductionFailure
from src.auth.models import User
from src.core.config import get_settings
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory

TRADING_DAY = date(2026, 8, 12)
EARLIER = date(2026, 8, 11)
NOW = datetime(2026, 8, 12, 22, 0, tzinfo=timezone.utc)

# Every symbol this module writes. Prefixed so the wipe below can take them all
# without touching anything another module seeded.
PREFIX = "DSP"
A, B, C, D = f"{PREFIX}AAA", f"{PREFIX}BBB", f"{PREFIX}CCC", f"{PREFIX}DDD"
SYMBOLS = (A, B, C, D)


@pytest.fixture(scope="module", autouse=True)
def alpha_schema():
    Base.metadata.create_all(
        sync_engine,
        tables=[
            Analysis.__table__,
            AnalysisRun.__table__,
            WatchlistEntry.__table__,
        ],
        checkfirst=True,
    )


@pytest.fixture(autouse=True)
def clean_rows():
    def wipe() -> None:
        with get_sync_db() as session:
            session.execute(delete(Analysis).where(Analysis.symbol.in_(SYMBOLS)))
            session.execute(delete(AnalysisRun).where(AnalysisRun.symbol.in_(SYMBOLS)))
            session.execute(
                delete(WatchlistEntry).where(WatchlistEntry.symbol.in_(SYMBOLS))
            )

    wipe()
    yield
    wipe()


@pytest.fixture
def session():
    session = sync_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def users():
    """A pool of users, since watcher counts are one of the ordering keys."""
    created: list[int] = []

    def make(count: int = 1) -> list[int]:
        ids: list[int] = []
        with get_sync_db() as inner:
            for _ in range(count):
                user = User(
                    email=f"dsp-{uuid.uuid4().hex[:12]}@example.com",
                    hashed_password="x",
                )
                inner.add(user)
                inner.flush()
                ids.append(user.id)
        created.extend(ids)
        return ids

    yield make

    with get_sync_db() as inner:
        for user_id in created:
            inner.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user_id))
            inner.execute(delete(User).where(User.id == user_id))


def queue(
    session,
    symbol: str,
    *,
    trading_day: date = TRADING_DAY,
    status: RunStatus = RunStatus.PENDING,
    origin: RunOrigin = RunOrigin.NIGHTLY,
    attempts: int = 0,
    requested_by: int | None = None,
    next_attempt_at: datetime | None = None,
) -> AnalysisRun:
    run = AnalysisRun(
        symbol=symbol,
        trading_day=trading_day,
        status=status.value,
        origin=origin.value,
        attempts=attempts,
        requested_by_user_id=requested_by,
        next_attempt_at=next_attempt_at,
    )
    session.add(run)
    session.commit()
    return run


def publish(session, symbol: str, trading_day: date) -> Analysis:
    row = Analysis(
        symbol=symbol,
        trading_day=trading_day,
        verdict="hold",
        payload={"evidence": {}},
        schema_version=1,
    )
    session.add(row)
    session.commit()
    return row


def watch(session, user_id: int, symbol: str) -> None:
    session.add(WatchlistEntry(user_id=user_id, symbol=symbol))
    session.commit()


def a_producer(verdict: str = "hold"):
    """A producer that succeeds and records what it was asked for."""
    seen: list[tuple[str, date]] = []

    def produce(symbol: str, trading_day: date) -> AnalysisDraft:
        seen.append((symbol, trading_day))
        return AnalysisDraft(verdict=verdict, payload={"evidence": {"symbol": symbol}})

    produce.seen = seen  # type: ignore[attr-defined]
    return produce


def a_failing_producer(code: str = "llm_transport_error", message: str = "route down"):
    def produce(symbol: str, trading_day: date) -> AnalysisDraft:
        raise ProductionFailure(code, message)

    return produce


def never_called(symbol: str, trading_day: date) -> AnalysisDraft:
    raise AssertionError("the producer ran for a pair that should not have been claimed")


class TestTheClaim:
    def test_it_takes_the_run_to_producing_and_counts_the_attempt(self, session):
        queue(session, A)

        claimed = claim_next_run(session, TRADING_DAY, now=NOW)

        assert claimed.symbol == A
        assert claimed.status == RunStatus.PRODUCING.value
        assert claimed.attempts == 1
        assert claimed.started_at is not None

    def test_a_second_claim_does_not_return_the_same_run(self, session):
        queue(session, A)

        first = claim_next_run(session, TRADING_DAY, now=NOW)
        second = claim_next_run(session, TRADING_DAY, now=NOW)

        assert first.symbol == A
        assert second is None

    def test_a_row_another_worker_holds_is_skipped_rather_than_waited_on(
        self, session
    ):
        """SKIP LOCKED, not FOR UPDATE: a second worker moves on, it does not block.

        The lock is taken in a transaction that stays open for the length of the
        assertion. Without SKIP LOCKED this call would wait on it rather than
        return, so the test would hang instead of failing — which is the honest
        shape of the thing being proven.
        """
        queue(session, A)
        holder = sync_session_factory()
        try:
            held = holder.execute(
                select(AnalysisRun)
                .where(AnalysisRun.symbol == A)
                .with_for_update()
            ).scalar_one()

            assert held.symbol == A
            assert claim_next_run(session, TRADING_DAY, now=NOW) is None
        finally:
            holder.rollback()
            holder.close()

    def test_it_moves_on_to_the_next_run_rather_than_stopping(self, session):
        queue(session, A)
        queue(session, B)
        holder = sync_session_factory()
        try:
            holder.execute(
                select(AnalysisRun)
                .where(AnalysisRun.symbol == A)
                .with_for_update()
            ).scalar_one()

            assert claim_next_run(session, TRADING_DAY, now=NOW).symbol == B
        finally:
            holder.rollback()
            holder.close()

    def test_two_workers_do_not_produce_the_same_pair_twice(self, session):
        """Past the lock, `producing` is the barrier and the constraint the last."""
        queue(session, A)
        other = sync_session_factory()
        try:
            first = claim_next_run(session, TRADING_DAY, now=NOW)
            second = claim_next_run(other, TRADING_DAY, now=NOW)
        finally:
            other.rollback()
            other.close()

        assert first.symbol == A
        assert second is None

    def test_a_producing_run_is_never_reclaimed(self, session):
        queue(session, A, status=RunStatus.PRODUCING)

        assert claim_next_run(session, TRADING_DAY, now=NOW) is None

    def test_a_run_at_the_ceiling_is_never_claimed(self, session):
        queue(
            session,
            A,
            status=RunStatus.FAILED,
            attempts=MAX_ATTEMPTS_PER_SESSION,
        )

        assert claim_next_run(session, TRADING_DAY, now=NOW) is None

    def test_a_run_scheduled_for_later_is_not_due_yet(self, session):
        queue(
            session,
            A,
            status=RunStatus.FAILED,
            attempts=1,
            next_attempt_at=NOW + timedelta(minutes=5),
        )

        assert claim_next_run(session, TRADING_DAY, now=NOW) is None
        assert (
            claim_next_run(session, TRADING_DAY, now=NOW + timedelta(minutes=6)).symbol
            == A
        )

    def test_another_trading_day_is_a_different_queue(self, session):
        queue(session, A, trading_day=EARLIER)

        assert claim_next_run(session, TRADING_DAY, now=NOW) is None


class TestTheOrdering:
    def test_on_demand_with_a_user_waiting_goes_first(self, session, users):
        user_id = users()[0]
        queue(session, A)
        queue(session, D, origin=RunOrigin.ON_DEMAND, requested_by=user_id)

        assert claim_next_run(session, TRADING_DAY, now=NOW).symbol == D

    def test_a_never_analysed_symbol_beats_one_with_a_prior_analysis(self, session):
        publish(session, A, EARLIER)
        queue(session, A)
        queue(session, B)

        assert claim_next_run(session, TRADING_DAY, now=NOW).symbol == B

    def test_the_oldest_prior_analysis_goes_first(self, session):
        publish(session, A, EARLIER)
        publish(session, B, EARLIER - timedelta(days=30))
        queue(session, A)
        queue(session, B)

        assert claim_next_run(session, TRADING_DAY, now=NOW).symbol == B

    def test_the_symbol_more_watchlists_carry_goes_first(self, session, users):
        first, second = users(2)
        watch(session, first, B)
        watch(session, second, B)
        watch(session, first, A)
        queue(session, A)
        queue(session, B)

        assert claim_next_run(session, TRADING_DAY, now=NOW).symbol == B

    def test_the_last_key_makes_the_order_total(self, session):
        """Two symbols equal on the first four still have one fixed order."""
        queue(session, C)
        queue(session, A)
        queue(session, B)

        drained = [
            claim_next_run(session, TRADING_DAY, now=NOW).symbol for _ in range(3)
        ]

        assert drained == [A, B, C]

    def test_the_order_is_reproducible(self, session, users):
        """The same queue drains the same way twice, keys and ties included."""
        user_id = users()[0]
        watch(session, user_id, C)
        publish(session, A, EARLIER)
        for symbol in (A, B, C):
            queue(session, symbol)

        first_pass = [
            claim_next_run(session, TRADING_DAY, now=NOW).symbol for _ in range(3)
        ]

        with get_sync_db() as reset:
            reset.execute(delete(AnalysisRun).where(AnalysisRun.symbol.in_(SYMBOLS)))
        for symbol in (C, A, B):  # inserted in a different order on purpose
            queue(session, symbol)

        second_pass = [
            claim_next_run(session, TRADING_DAY, now=NOW).symbol for _ in range(3)
        ]

        assert first_pass == second_pass


class TestDraining:
    def test_it_produces_every_claimable_run_in_order(self, session):
        for symbol in (B, A):
            queue(session, symbol)
        producer = a_producer()

        report = drain_queue(session, producer, trading_day=TRADING_DAY, now=NOW)

        assert report.produced == [A, B]
        assert [symbol for symbol, _ in producer.seen] == [A, B]
        assert (
            stored_run(session, A, TRADING_DAY).status == RunStatus.READY.value
        )

    def test_an_analysis_that_already_exists_is_repaired_without_producing(
        self, session
    ):
        queue(session, A, status=RunStatus.PRODUCING)
        publish(session, A, TRADING_DAY)
        # Back to pending so it is claimable: what is under test is the repair,
        # not the sweep that would have got it there.
        run = stored_run(session, A, TRADING_DAY)
        run.status = RunStatus.PENDING.value
        session.commit()

        report = drain_queue(session, never_called, trading_day=TRADING_DAY, now=NOW)

        assert report.repaired == [A]
        assert report.produced == []
        assert stored_run(session, A, TRADING_DAY).status == RunStatus.READY.value

    def test_a_limit_bounds_one_pass_and_leaves_the_rest_queued(self, session):
        for symbol in (A, B, C):
            queue(session, symbol)

        report = drain_queue(
            session, a_producer(), trading_day=TRADING_DAY, now=NOW, limit=2
        )

        assert report.produced == [A, B]
        assert stored_run(session, C, TRADING_DAY).status == RunStatus.PENDING.value

    def test_nothing_is_produced_for_a_day_the_store_does_not_hold(self, session):
        report = drain_queue(session, never_called, trading_day=None, now=NOW)

        assert report.claimed == 0
        assert report.produced == []

    def test_no_analysis_is_dated_to_a_previous_trading_day(self, session):
        """The deadline is a reporting boundary; nothing here relabels."""
        queue(session, A)
        producer = a_producer()

        drain_queue(session, producer, trading_day=TRADING_DAY, now=NOW)

        assert producer.seen == [(A, TRADING_DAY)]
        published = session.execute(
            select(Analysis).where(Analysis.symbol == A)
        ).scalars().all()
        assert [row.trading_day for row in published] == [TRADING_DAY]


class TestShutdown:
    def test_an_in_flight_run_is_never_preempted(self, session):
        """Stop is checked between runs, so the one in flight finishes."""
        for symbol in (A, B, C):
            queue(session, symbol)
        stopped: list[str] = []

        def produce(symbol: str, trading_day: date) -> AnalysisDraft:
            stopped.append(symbol)
            return AnalysisDraft(verdict="hold", payload={})

        report = drain_queue(
            session,
            produce,
            trading_day=TRADING_DAY,
            now=NOW,
            should_stop=lambda: len(stopped) >= 1,
        )

        assert report.produced == [A]
        assert stored_run(session, A, TRADING_DAY).status == RunStatus.READY.value
        assert stored_run(session, B, TRADING_DAY).status == RunStatus.PENDING.value


class TestTheBackoff:
    def test_the_first_attempt_waits_for_nothing(self, session):
        """Readiness gated it, so a fresh run is due the moment it is queued."""
        queue(session, A)
        producer = a_producer()

        drain_queue(session, producer, trading_day=TRADING_DAY, now=NOW)

        assert producer.seen == [(A, TRADING_DAY)]

    def test_a_first_failure_waits_five_minutes(self, session):
        queue(session, A)

        drain_queue(
            session, a_failing_producer(), trading_day=TRADING_DAY, now=NOW
        )
        run = stored_run(session, A, TRADING_DAY)

        assert run.attempts == 1
        assert run.next_attempt_at == NOW + timedelta(minutes=BACKOFF_MINUTES[0])

    def test_a_second_failure_waits_thirty(self, session):
        queue(session, A)
        failing = a_failing_producer()

        drain_queue(session, failing, trading_day=TRADING_DAY, now=NOW)
        second_due = NOW + timedelta(minutes=BACKOFF_MINUTES[0])
        drain_queue(session, failing, trading_day=TRADING_DAY, now=second_due)
        run = stored_run(session, A, TRADING_DAY)

        assert run.attempts == 2
        assert run.next_attempt_at == second_due + timedelta(
            minutes=BACKOFF_MINUTES[1]
        )

    def test_the_third_failure_names_no_further_time(self, session):
        queue(session, A, status=RunStatus.FAILED, attempts=2)
        failing = a_failing_producer()

        drain_queue(session, failing, trading_day=TRADING_DAY, now=NOW)
        run = stored_run(session, A, TRADING_DAY)

        assert run.attempts == MAX_ATTEMPTS_PER_SESSION
        # At the ceiling there is no fourth attempt, so there is no time to name.
        assert run.next_attempt_at is None

    def test_a_restart_before_the_deadline_resumes_the_schedule(self, session):
        """The schedule is a column, so a new session reads it back unchanged."""
        queue(session, A)
        drain_queue(
            session, a_failing_producer(), trading_day=TRADING_DAY, now=NOW
        )

        restarted = sync_session_factory()
        try:
            due = restarted.execute(
                select(AnalysisRun.next_attempt_at).where(AnalysisRun.symbol == A)
            ).scalar_one()
            early = drain_queue(
                restarted,
                never_called,
                trading_day=TRADING_DAY,
                now=NOW + timedelta(minutes=1),
            )
            on_time = drain_queue(
                restarted,
                a_producer(),
                trading_day=TRADING_DAY,
                now=NOW + timedelta(minutes=6),
            )
        finally:
            restarted.close()

        assert due == NOW + timedelta(minutes=5)
        assert early.claimed == 0
        assert on_time.produced == [A]

    def test_a_fourth_attempt_is_never_dispatched_in_the_same_session(self, session):
        queue(session, A, status=RunStatus.FAILED, attempts=MAX_ATTEMPTS_PER_SESSION)

        report = drain_queue(
            session,
            never_called,
            trading_day=TRADING_DAY,
            now=NOW + timedelta(hours=2),
        )

        assert report.claimed == 0

    def test_a_failure_keeps_its_code_and_a_bounded_one_line_reason(self, session):
        queue(session, A)

        drain_queue(
            session,
            a_failing_producer("invalid_model_output", "fragment\nstill invalid"),
            trading_day=TRADING_DAY,
            now=NOW,
        )
        run = stored_run(session, A, TRADING_DAY)

        assert run.status == RunStatus.FAILED.value
        assert run.error_code == "invalid_model_output"
        assert "\n" not in run.error_message


class TestAuthUnavailable:
    def test_it_pauses_the_whole_route_rather_than_failing_a_symbol(self, session):
        queue(session, A)
        queue(session, B)

        report = drain_queue(
            session,
            a_failing_producer("auth_unavailable", "the route rejected the key"),
            trading_day=TRADING_DAY,
            now=NOW,
        )

        assert report.paused_until == NOW + timedelta(minutes=AUTH_PROBE_MINUTES)
        assert report.failed == []
        for symbol in (A, B):
            run = stored_run(session, symbol, TRADING_DAY)
            assert run.status == RunStatus.PENDING.value
            assert run.error_code is None
            assert run.next_attempt_at == NOW + timedelta(minutes=AUTH_PROBE_MINUTES)

    def test_it_records_one_condition_rather_than_one_failure_per_symbol(
        self, session
    ):
        for symbol in (A, B, C, D):
            queue(session, symbol)
        calls: list[str] = []

        def refusing(symbol: str, trading_day: date) -> AnalysisDraft:
            calls.append(symbol)
            raise ProductionFailure("auth_unavailable", "no credential")

        drain_queue(session, refusing, trading_day=TRADING_DAY, now=NOW)

        assert calls == [A]
        assert [
            stored_run(session, symbol, TRADING_DAY).attempts
            for symbol in (B, C, D)
        ] == [0, 0, 0]

    def test_the_dispatcher_probes_again_after_fifteen_minutes(self, session):
        queue(session, A)
        drain_queue(
            session,
            a_failing_producer("auth_unavailable", "no credential"),
            trading_day=TRADING_DAY,
            now=NOW,
        )

        early = drain_queue(
            session,
            never_called,
            trading_day=TRADING_DAY,
            now=NOW + timedelta(minutes=AUTH_PROBE_MINUTES - 1),
        )
        recovered = drain_queue(
            session,
            a_producer(),
            trading_day=TRADING_DAY,
            now=NOW + timedelta(minutes=AUTH_PROBE_MINUTES),
        )

        assert early.claimed == 0
        assert recovered.produced == [A]

    def test_the_pause_never_pulls_a_longer_backoff_forward(self, session):
        later = NOW + timedelta(minutes=30)
        queue(session, B, status=RunStatus.FAILED, attempts=2, next_attempt_at=later)
        queue(session, A)

        drain_queue(
            session,
            a_failing_producer("auth_unavailable", "no credential"),
            trading_day=TRADING_DAY,
            now=NOW,
        )

        assert stored_run(session, B, TRADING_DAY).next_attempt_at == later

    def test_the_attempt_it_spent_is_not_refunded(self, session):
        """It reached the route and was turned away, which is an attempt that ran."""
        queue(session, A)

        drain_queue(
            session,
            a_failing_producer("auth_unavailable", "no credential"),
            trading_day=TRADING_DAY,
            now=NOW,
        )

        assert stored_run(session, A, TRADING_DAY).attempts == 1


class TestTheDeadline:
    def test_an_evening_that_lost_a_symbol_reports_partial(self, session):
        queue(session, A)
        queue(session, B)
        drain_queue(session, a_producer(), trading_day=TRADING_DAY, now=NOW, limit=1)
        drain_queue(
            session,
            a_failing_producer(),
            trading_day=TRADING_DAY,
            now=NOW,
        )
        # Past the ceiling, so nothing is outstanding and the evening is over.
        run = stored_run(session, B, TRADING_DAY)
        run.attempts = MAX_ATTEMPTS_PER_SESSION
        session.commit()

        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.PARTIAL
        assert status.ready == 1
        assert status.failed == 1

    def test_a_trading_day_with_no_runs_reports_blocked(self, session):
        assert (
            cohort_state(session, TRADING_DAY - timedelta(days=400)).state
            is CohortState.BLOCKED
        )


class TestTheScheduledJob:
    @pytest.mark.asyncio
    async def test_it_stays_silent_while_alpha_desk_is_off(self, monkeypatch):
        """The one job in this package that spends money is gated on that flag."""
        monkeypatch.setenv("ALPHA_DESK_ENABLED", "false")
        get_settings.cache_clear()
        try:
            assert await drain_analysis_queue() == {"skipped": "alpha_desk_disabled"}
        finally:
            monkeypatch.undo()
            get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_a_tick_that_fails_does_not_take_the_scheduler_down(
        self, monkeypatch
    ):
        monkeypatch.setenv("ALPHA_DESK_ENABLED", "true")
        get_settings.cache_clear()

        def exploding(*args, **kwargs):
            raise RuntimeError("the route is unreachable")

        monkeypatch.setattr("src.alpha.jobs.analysis_producer", exploding)
        try:
            assert "error" in await drain_analysis_queue()
        finally:
            monkeypatch.undo()
            get_settings.cache_clear()


class TestTheSweepBesideIt:
    def test_the_dispatcher_grows_no_sweep_of_its_own(self, session):
        """A stuck run is A2's to clear; two writers would race over one row."""
        queue(session, A, status=RunStatus.PRODUCING)

        report = drain_queue(
            session,
            never_called,
            trading_day=TRADING_DAY,
            now=NOW + timedelta(hours=6),
        )

        assert report.claimed == 0
        assert stored_run(session, A, TRADING_DAY).status == RunStatus.PRODUCING.value
