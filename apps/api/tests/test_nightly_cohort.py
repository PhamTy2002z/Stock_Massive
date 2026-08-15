"""The cohort an evening captures, and the state it is read back in.

Four claims carry this ticket, and each of them is a thing somebody would
reasonably implement the other way —

*The cohort is captured by data.* The moment a Market Snapshot establishes a new
Trading Day, every watched symbol is queued. A clock cannot do it: the Main
Source appends the session hours after the close, so a cohort captured on the
hour would be a cohort for a day that does not exist yet.

*Capturing twice captures nothing.* The idempotency is
``UNIQUE(symbol, trading_day)`` and not a flag anybody keeps, so a second
Snapshot, a restart and two concurrent captures all end the same way.

*Removing a symbol afterwards changes nothing.* An Analysis is keyed by
``(symbol, trading_day)`` and shared, so it was never that user's to cancel.

*The state has no table.* It is derived from the runs, which already carry
status and origin. ``blocked`` is reserved for the one evening that had no
session to be run against, and it is neither a synonym for failed nor the answer
for an evening nobody watched a symbol in.

Run against a live Postgres: two of these are about what the database refuses.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from src.alpha.analysis_run import RunOrigin, RunStatus
from src.alpha.models import Analysis, AnalysisRun, WatchlistEntry
from src.alpha.nightly import (
    CohortState,
    capture_nightly_cohort,
    cohort_state,
    watchlist_union,
)
from src.alpha.on_demand import (
    ON_DEMAND_ANALYSES_PER_DAY,
    OnDemandOutcome,
    on_demand_analyses_used,
    request_on_demand_analysis,
)
from src.auth.models import User
from src.core.config import get_settings
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.stocks.universe import forget_cohort_cache

WATCHED = ("COHA", "COHB", "COHC")
UNWATCHED = "COHD"
DROPPED = "COHE"
ALL_SYMBOLS = WATCHED + (UNWATCHED, DROPPED)
TRADING_DAY = date(2026, 8, 14)
EARLIER_DAY = date(2026, 8, 13)


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
def declared_universe(monkeypatch):
    """Every test symbol in the Universe unless a test narrows it."""

    def declare(*symbols: str) -> None:
        monkeypatch.setenv("UNIVERSE_SYMBOLS", ",".join(symbols))
        get_settings.cache_clear()
        forget_cohort_cache()

    declare(*ALL_SYMBOLS)
    yield declare
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


@pytest.fixture(autouse=True)
def clean_rows():
    def wipe() -> None:
        with get_sync_db() as session:
            session.execute(delete(Analysis).where(Analysis.symbol.in_(ALL_SYMBOLS)))
            session.execute(
                delete(AnalysisRun).where(AnalysisRun.symbol.in_(ALL_SYMBOLS))
            )
            session.execute(
                delete(WatchlistEntry).where(WatchlistEntry.symbol.in_(ALL_SYMBOLS))
            )

    wipe()
    yield
    wipe()


@pytest.fixture(autouse=True)
def pinned_trading_day(monkeypatch):
    """The session the on-demand lane resolves for itself, pinned to this test's.

    Patched rather than passed: the lane takes a user and a symbol and nothing
    else, precisely so no caller can aim it at a session that has not closed.
    That is the guarantee under test elsewhere, so a test that needed a parameter
    here would be asking for the code path the lane exists to not have.
    """
    monkeypatch.setattr(
        "src.alpha.on_demand.latest_trading_day", lambda session: TRADING_DAY
    )


@pytest.fixture
def session():
    session = sync_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def users(session):
    """Two accounts, so a shared symbol has two watchers."""
    created: list[int] = []

    def make() -> int:
        user = User(
            email=f"cohort-{uuid.uuid4().hex[:12]}@example.com", hashed_password="x"
        )
        session.add(user)
        session.commit()
        created.append(user.id)
        return user.id

    first, second = make(), make()
    yield first, second
    for user_id in created:
        session.execute(delete(User).where(User.id == user_id))
    session.commit()


def watch(session, user_id: int, *symbols: str) -> None:
    for symbol in symbols:
        session.add(WatchlistEntry(user_id=user_id, symbol=symbol))
    session.commit()


def runs_for(session, trading_day: date = TRADING_DAY) -> dict[str, AnalysisRun]:
    rows = session.execute(
        select(AnalysisRun).where(
            AnalysisRun.trading_day == trading_day,
            AnalysisRun.symbol.in_(ALL_SYMBOLS),
        )
    ).scalars()
    return {row.symbol: row for row in rows}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestTheUnion:
    def test_it_is_every_watchlist_deduplicated(self, session, users):
        first, second = users
        watch(session, first, "COHA", "COHB")
        watch(session, second, "COHB", "COHC")

        assert watchlist_union(session) == ("COHA", "COHB", "COHC")

    def test_a_symbol_nobody_watches_is_not_in_it(self, session, users):
        watch(session, users[0], "COHA")
        assert UNWATCHED not in watchlist_union(session)

    def test_a_symbol_the_universe_dropped_is_not_queued(
        self, session, users, declared_universe
    ):
        """`unsupported` produces nothing, so queueing it would mint a run that
        can only fail."""
        watch(session, users[0], "COHA", DROPPED)
        declared_universe("COHA", "COHB", "COHC", UNWATCHED)

        assert watchlist_union(session) == ("COHA",)


class TestTheCapture:
    def test_it_queues_one_pending_nightly_run_per_watched_symbol(
        self, session, users
    ):
        watch(session, users[0], *WATCHED)

        capture = capture_nightly_cohort(session, TRADING_DAY)

        assert capture.created == WATCHED
        queued = runs_for(session)
        assert set(queued) == set(WATCHED)
        for run in queued.values():
            assert run.status == RunStatus.PENDING.value
            assert run.origin == RunOrigin.NIGHTLY.value
            assert run.attempts == 0
            assert run.requested_by_user_id is None

    def test_two_users_watching_one_symbol_produce_exactly_one_run(
        self, session, users
    ):
        first, second = users
        watch(session, first, "COHA")
        watch(session, second, "COHA")

        capture_nightly_cohort(session, TRADING_DAY)

        rows = session.execute(
            select(AnalysisRun).where(
                AnalysisRun.symbol == "COHA", AnalysisRun.trading_day == TRADING_DAY
            )
        ).scalars().all()
        assert len(rows) == 1

    def test_a_second_snapshot_for_the_same_day_captures_nothing(
        self, session, users
    ):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)

        again = capture_nightly_cohort(session, TRADING_DAY)

        assert again.created == ()
        assert again.joined == WATCHED
        assert len(runs_for(session)) == len(WATCHED)

    def test_a_new_trading_day_captures_a_cohort_of_its_own(self, session, users):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, EARLIER_DAY)

        capture_nightly_cohort(session, TRADING_DAY)

        assert set(runs_for(session, EARLIER_DAY)) == set(WATCHED)
        assert set(runs_for(session, TRADING_DAY)) == set(WATCHED)

    def test_nothing_is_captured_where_no_trading_day_was_established(
        self, session, users, monkeypatch
    ):
        watch(session, users[0], *WATCHED)
        monkeypatch.setattr(
            "src.alpha.nightly.latest_trading_day", lambda session: None
        )

        capture = capture_nightly_cohort(session)

        assert capture.trading_day is None
        assert capture.created == ()
        assert runs_for(session) == {}

    def test_an_empty_evening_captures_nothing_and_says_so(self, session):
        capture = capture_nightly_cohort(session, TRADING_DAY)

        assert capture.trading_day == TRADING_DAY
        assert capture.created == ()
        assert not capture.captured

    def test_it_joins_a_run_the_on_demand_lane_already_created(
        self, session, users
    ):
        """Adding a symbol before the cohort forms costs the evening nothing."""
        watch(session, users[0], "COHA")
        session.add(
            AnalysisRun(
                symbol="COHA",
                trading_day=TRADING_DAY,
                status=RunStatus.READY.value,
                origin=RunOrigin.ON_DEMAND.value,
                attempts=1,
                requested_by_user_id=users[0],
            )
        )
        session.commit()

        capture = capture_nightly_cohort(session, TRADING_DAY)

        assert capture.created == ()
        assert capture.joined == ("COHA",)
        # The origin is not rewritten: who caused a run is written once.
        assert runs_for(session)["COHA"].origin == RunOrigin.ON_DEMAND.value


class TestWhatHappensAfterCapture:
    def test_removing_a_symbol_leaves_its_run_untouched(self, session, users):
        """The Analysis is shared, so it was never that user's to cancel."""
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)

        session.execute(
            delete(WatchlistEntry).where(
                WatchlistEntry.user_id == users[0],
                WatchlistEntry.symbol == "COHB",
            )
        )
        session.commit()

        run = runs_for(session)["COHB"]
        assert run.status == RunStatus.PENDING.value
        assert run.origin == RunOrigin.NIGHTLY.value

    def test_a_symbol_added_after_capture_takes_the_on_demand_lane(
        self, session, users
    ):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)

        result = request_on_demand_analysis(session, users[0], UNWATCHED)

        assert result.outcome is OnDemandOutcome.CREATED
        assert runs_for(session, result.trading_day)[UNWATCHED].origin == (
            RunOrigin.ON_DEMAND.value
        )

    def test_adding_a_symbol_the_cohort_already_holds_costs_nothing(
        self, session, users
    ):
        """A2's rule, still holding once there is a cohort to collide with."""
        watch(session, users[1], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)

        before = on_demand_analyses_used(session, users[0], TRADING_DAY)
        result = request_on_demand_analysis(session, users[0], "COHA")

        assert result.outcome is OnDemandOutcome.ALREADY_QUEUED
        assert result.remaining == ON_DEMAND_ANALYSES_PER_DAY
        assert on_demand_analyses_used(session, users[0], TRADING_DAY) == before

    def test_joining_does_not_rewrite_the_run_that_is_already_there(
        self, session, users
    ):
        watch(session, users[1], "COHA")
        capture_nightly_cohort(session, TRADING_DAY)

        request_on_demand_analysis(session, users[0], "COHA")

        run = runs_for(session)["COHA"]
        assert run.origin == RunOrigin.NIGHTLY.value
        assert run.requested_by_user_id is None


class TestTheDerivedState:
    def test_no_trading_day_at_all_is_blocked(self, session, monkeypatch):
        """Not the same as failed: nothing was attempted."""
        monkeypatch.setattr(
            "src.alpha.nightly.latest_trading_day", lambda session: None
        )

        status = cohort_state(session)

        assert status.state is CohortState.BLOCKED
        assert status.trading_day is None
        assert status.total == 0

    def test_a_day_nobody_watches_a_symbol_for_is_complete_and_not_blocked(
        self, session
    ):
        """An operator seeing `blocked` goes and looks at the Collector.

        An evening where nobody watches a symbol has a perfectly good session
        and nothing to do with it, so answering `blocked` there would send them
        to exactly the wrong place. `total: 0` is what says which kind of
        finished evening it was.
        """
        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.COMPLETE
        assert status.total == 0
        assert status.trading_day == TRADING_DAY

    def test_a_cohort_with_work_left_is_running(self, session, users):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)

        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.RUNNING
        assert status.pending == len(WATCHED)
        assert status.total == len(WATCHED)

    def test_a_cohort_still_producing_is_running(self, session, users):
        watch(session, users[0], "COHA")
        capture_nightly_cohort(session, TRADING_DAY)
        _set_status(session, "COHA", RunStatus.PRODUCING)

        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.RUNNING
        assert status.producing == 1

    def test_every_run_ready_is_complete(self, session, users):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)
        for symbol in WATCHED:
            _set_status(session, symbol, RunStatus.READY)

        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.COMPLETE
        assert status.ready == len(WATCHED)

    def test_one_failure_among_finished_runs_is_partial(self, session, users):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)
        _set_status(session, "COHA", RunStatus.FAILED)
        _set_status(session, "COHB", RunStatus.READY)
        _set_status(session, "COHC", RunStatus.READY)

        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.PARTIAL
        assert (status.ready, status.failed) == (2, 1)

    def test_an_evening_that_lost_everything_is_still_partial(self, session, users):
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)
        for symbol in WATCHED:
            _set_status(session, symbol, RunStatus.FAILED)

        assert cohort_state(session, TRADING_DAY).state is CohortState.PARTIAL

    def test_an_on_demand_run_counts_as_work_outstanding_for_that_day(
        self, session, users
    ):
        """Reported per origin, a cohort would read complete with rows in the queue."""
        watch(session, users[0], "COHA")
        capture_nightly_cohort(session, TRADING_DAY)
        _set_status(session, "COHA", RunStatus.READY)
        request_on_demand_analysis(session, users[0], UNWATCHED)

        status = cohort_state(session, TRADING_DAY)

        assert status.state is CohortState.RUNNING
        assert status.pending == 1

    def test_the_state_is_read_off_the_runs_and_needs_no_table(self):
        """No new model, so no Alembic revision. Asserted, since it is the ticket."""
        from src.alpha import models

        tables = {
            value.__tablename__
            for value in vars(models).values()
            if hasattr(value, "__tablename__")
        }
        assert "analysis_cohort" not in tables
        assert "nightly_cohort" not in tables

    def test_blocked_is_reserved_for_the_one_condition_that_earns_it(
        self, session, users, monkeypatch
    ):
        """No Trading Day, and nothing else. Every other evening has a session."""
        watch(session, users[0], *WATCHED)
        capture_nightly_cohort(session, TRADING_DAY)
        monkeypatch.setattr(
            "src.alpha.nightly.latest_trading_day", lambda session: None
        )

        assert cohort_state(session).state is CohortState.BLOCKED
        assert cohort_state(session, TRADING_DAY).state is CohortState.RUNNING


class TestNoMigrationWasAdded:
    def test_the_revision_chain_is_the_one_a2_left(self):
        """This ticket says so in as many words: no Alembic revision is added."""
        from pathlib import Path

        versions = Path(__file__).parents[1] / "alembic" / "versions"
        added = [
            path.name
            for path in versions.glob("*.py")
            if "cohort" in path.name.lower() and "profit" not in path.name.lower()
        ]
        assert added == []


def _set_status(session, symbol: str, status: RunStatus) -> None:
    run = runs_for(session)[symbol]
    run.status = status.value
    run.finished_at = _now() if status in (RunStatus.READY, RunStatus.FAILED) else None
    if status is RunStatus.FAILED:
        run.error_code = "llm_transport_error"
        run.error_message = "Tuyến LLM không trả lời được."
    session.commit()
