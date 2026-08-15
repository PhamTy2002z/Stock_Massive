"""How an Analysis gets produced exactly once, without machinery for it.

Two invariants carry the whole lifecycle, and every test here is one of them
seen from a different angle:

*A row in ``analysis`` existing means it is complete.* In-flight state lives
only in ``analysis_run``. That is what makes "serve yesterday instantly while
today runs" need no mechanism — newest row wins, and there is never a
half-written Analysis to filter out.

*A run marked ready implies the Analysis row exists.* So the Analysis is written
first and the status flipped second. Dying in between leaves the run
``producing``; the retry finds the Analysis already there and flips the status
without producing again. **Idempotency is a consequence of the constraint, not
extra code** — which is a claim that has to be tested by actually killing the
process between the two writes, not by reading the code.

The producer is a stub. This ticket owns the state machine; generation, the
evidence envelope and the LLM call are a later milestone's, and the seam is a
parameter precisely so that milestone changes nothing here.

Run against a live Postgres: what is under test includes what the database
refuses.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from src.alpha.analysis_run import (
    ABANDONED_CODE,
    MAX_ATTEMPTS_PER_SESSION,
    RUN_ERROR_CODES,
    AnalysisRefusal,
    RunOrigin,
    RunStatus,
    mark_run_ready,
    produce_analysis,
    retry_analysis,
    sweep_stuck_runs,
)
from src.alpha.models import Analysis, AnalysisRun, WatchlistEntry
from src.alpha.producer import (
    FAILURE_CODES,
    AnalysisDraft,
    ProductionFailure,
    stub_producer,
)
from src.auth.models import User
from src.core.config import get_settings
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.stocks.universe import forget_cohort_cache

SYMBOL = "RUNSYM"
OTHER = "RUNOTH"
TRADING_DAY = date(2026, 8, 14)
EARLIER_DAY = date(2026, 8, 13)
NOW = datetime(2026, 8, 14, 18, 0, tzinfo=timezone.utc)


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
    """Both test symbols in the Universe unless a test says otherwise."""

    def declare(*symbols: str) -> None:
        monkeypatch.setenv("UNIVERSE_SYMBOLS", ",".join(symbols))
        get_settings.cache_clear()
        forget_cohort_cache()

    declare(SYMBOL, OTHER)
    yield declare
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


@pytest.fixture(autouse=True)
def clean_rows():
    """Everything written under the test symbols, removed either side."""

    def wipe() -> None:
        with get_sync_db() as session:
            session.execute(delete(Analysis).where(Analysis.symbol.in_([SYMBOL, OTHER])))
            session.execute(
                delete(AnalysisRun).where(AnalysisRun.symbol.in_([SYMBOL, OTHER]))
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
def watcher(session):
    """A user watching SYMBOL, since only a watcher may retry."""
    created: list[int] = []

    def make(*symbols: str) -> int:
        with get_sync_db() as inner:
            user = User(
                email=f"run-{uuid.uuid4().hex[:12]}@example.com", hashed_password="x"
            )
            inner.add(user)
            inner.flush()
            for symbol in symbols:
                inner.add(WatchlistEntry(user_id=user.id, symbol=symbol))
            created.append(user.id)
            return user.id

    yield make

    with get_sync_db() as inner:
        for user_id in created:
            inner.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user_id))
            inner.execute(delete(User).where(User.id == user_id))


def verdict_producer(verdict: str = "accumulate"):
    """A producer that succeeds, and says what it said."""

    def produce(symbol: str, trading_day: date) -> AnalysisDraft:
        return AnalysisDraft(
            verdict=verdict,
            payload={"symbol": symbol, "trading_day": trading_day.isoformat()},
        )

    return produce


def failing_producer(code: str = "missing_market_snapshot", message: str = "no session data for RUNSYM"):
    def produce(symbol: str, trading_day: date) -> AnalysisDraft:
        raise ProductionFailure(code=code, message=message)

    return produce


def refuses_to_run(symbol: str, trading_day: date) -> AnalysisDraft:
    """A producer whose being called at all is the failure."""
    raise AssertionError("the producer was called when the Analysis already existed")


def _run(session, symbol: str = SYMBOL, trading_day: date = TRADING_DAY) -> AnalysisRun:
    session.expire_all()
    return session.execute(
        select(AnalysisRun).where(
            AnalysisRun.symbol == symbol, AnalysisRun.trading_day == trading_day
        )
    ).scalar_one()


def _analyses(session, symbol: str = SYMBOL) -> list[Analysis]:
    session.expire_all()
    return list(
        session.execute(
            select(Analysis).where(Analysis.symbol == symbol).order_by(Analysis.id)
        ).scalars()
    )


class TestPublishing:
    """The Analysis is written first; the status is flipped second."""

    def test_a_successful_run_publishes_and_then_goes_ready(self, session):
        outcome = produce_analysis(
            session, SYMBOL, TRADING_DAY, verdict_producer("accumulate")
        )

        assert outcome.status is RunStatus.READY
        assert outcome.produced is True
        assert outcome.analysis.verdict == "accumulate"
        assert _run(session).status == RunStatus.READY.value
        assert _run(session).finished_at is not None

    def test_the_run_records_its_origin_and_its_attempt(self, session):
        produce_analysis(
            session, SYMBOL, TRADING_DAY, verdict_producer(), origin=RunOrigin.NIGHTLY
        )

        run = _run(session)
        assert run.origin == RunOrigin.NIGHTLY.value
        assert run.attempts == 1
        assert run.started_at is not None

    def test_a_death_between_the_two_writes_leaves_the_analysis_published(
        self, session, monkeypatch
    ):
        """The process dies after the Analysis is committed and before the run
        is flipped. The Analysis is complete; the run is the only thing wrong."""
        monkeypatch.setattr(
            "src.alpha.analysis_run.mark_run_ready",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(KeyboardInterrupt):
            produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer("hold"))

        assert _run(session).status == RunStatus.PRODUCING.value
        assert [a.verdict for a in _analyses(session)] == ["hold"]

    def test_the_retry_after_that_death_repairs_the_run_without_producing_again(
        self, session, monkeypatch
    ):
        monkeypatch.setattr(
            "src.alpha.analysis_run.mark_run_ready",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(KeyboardInterrupt):
            produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer("hold"))
        monkeypatch.undo()

        outcome = produce_analysis(session, SYMBOL, TRADING_DAY, refuses_to_run)

        assert outcome.status is RunStatus.READY
        assert outcome.produced is False
        assert _run(session).status == RunStatus.READY.value
        assert _run(session).attempts == 1
        assert [a.verdict for a in _analyses(session)] == ["hold"]

    def test_the_run_is_updated_in_place_while_analyses_only_accumulate(self, session):
        produce_analysis(session, SYMBOL, EARLIER_DAY, verdict_producer("hold"))
        produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer("reduce"))

        session.expire_all()
        runs = session.execute(
            select(AnalysisRun).where(AnalysisRun.symbol == SYMBOL)
        ).scalars().all()
        assert len(runs) == 2
        assert [a.trading_day for a in _analyses(session)] == [EARLIER_DAY, TRADING_DAY]


class TestRerun:
    """A rerun of a ready pair is a no-op, and v1 never overwrites."""

    def test_a_rerun_returns_the_existing_analysis_and_produces_nothing(self, session):
        first = produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer("hold"))

        again = produce_analysis(session, SYMBOL, TRADING_DAY, refuses_to_run)

        assert again.produced is False
        assert again.analysis.id == first.analysis.id

    def test_a_published_analysis_is_never_silently_overwritten(self, session):
        """Correcting one would need its own versioning decision, so a producer
        with a different opinion changes nothing."""
        produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer("hold"))

        produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer("avoid"))

        assert [a.verdict for a in _analyses(session)] == ["hold"]

    def test_two_callers_racing_for_one_pair_end_with_one_analysis(self, session):
        """Idempotency falls out of `UNIQUE(symbol, trading_day)`: whoever loses
        the insert reads the winner's row rather than producing a second."""
        with get_sync_db() as other:
            other.add(
                Analysis(
                    symbol=SYMBOL,
                    trading_day=TRADING_DAY,
                    verdict="watch",
                    payload={},
                    schema_version=1,
                )
            )

        outcome = produce_analysis(session, SYMBOL, TRADING_DAY, refuses_to_run)

        assert outcome.analysis.verdict == "watch"
        assert len(_analyses(session)) == 1


class TestFailure:
    """A failure is a code plus a sentence, and never a stack trace."""

    def test_a_failed_run_carries_a_stable_code_and_a_readable_reason(self, session):
        outcome = produce_analysis(
            session,
            SYMBOL,
            TRADING_DAY,
            failing_producer("missing_market_snapshot", "no session data for RUNSYM"),
        )

        assert outcome.status is RunStatus.FAILED
        run = _run(session)
        assert run.error_code == "missing_market_snapshot"
        assert run.error_message == "no session data for RUNSYM"
        assert run.finished_at is not None
        assert _analyses(session) == []

    def test_the_stored_reason_carries_no_traceback(self, session):
        produce_analysis(
            session, SYMBOL, TRADING_DAY, failing_producer(message="LLM route did not respond")
        )

        stored = _run(session).error_message
        assert "Traceback" not in stored
        assert "File \"" not in stored
        assert ".py" not in stored

    def test_an_unnamed_crash_is_not_dressed_up_as_a_failure_code(self, session):
        """The taxonomy has no code for "something we did not anticipate", and
        inventing one would put a lie in the error column. A crash propagates
        and leaves the run `producing` for the sweep to find."""

        def explodes(symbol: str, trading_day: date) -> AnalysisDraft:
            raise ZeroDivisionError("division by zero")

        with pytest.raises(ZeroDivisionError):
            produce_analysis(session, SYMBOL, TRADING_DAY, explodes)

        assert _run(session).status == RunStatus.PRODUCING.value
        assert _run(session).error_code is None


class TestRetryCeiling:
    """Three attempts per symbol per session, then locked until the next one."""

    def test_the_third_failure_locks_the_pair(self, session, watcher):
        """The failure that reaches the ceiling says so in its own outcome, so
        the interface can drop the retry action then rather than after one more
        press that does nothing."""
        user_id = watcher(SYMBOL)
        attempts = [
            retry_analysis(session, user_id, SYMBOL, TRADING_DAY, failing_producer())
            for _ in range(MAX_ATTEMPTS_PER_SESSION)
        ]

        assert [outcome.status for outcome in attempts] == [RunStatus.FAILED] * 3
        assert [outcome.locked for outcome in attempts] == [False, False, True]

        after = retry_analysis(session, user_id, SYMBOL, TRADING_DAY, refuses_to_run)

        assert after.locked is True
        assert _run(session).attempts == MAX_ATTEMPTS_PER_SESSION

    def test_the_lock_surfaces_the_reason_the_last_attempt_gave(self, session, watcher):
        user_id = watcher(SYMBOL)
        for _ in range(MAX_ATTEMPTS_PER_SESSION):
            retry_analysis(
                session,
                user_id,
                SYMBOL,
                TRADING_DAY,
                failing_producer(message="no session data for RUNSYM"),
            )

        locked = retry_analysis(session, user_id, SYMBOL, TRADING_DAY, refuses_to_run)

        assert locked.error_message == "no session data for RUNSYM"

    def test_the_next_session_starts_with_a_fresh_allowance(self, session, watcher):
        user_id = watcher(SYMBOL)
        for _ in range(MAX_ATTEMPTS_PER_SESSION):
            retry_analysis(session, user_id, SYMBOL, EARLIER_DAY, failing_producer())

        outcome = retry_analysis(
            session, user_id, SYMBOL, TRADING_DAY, verdict_producer("hold")
        )

        assert outcome.status is RunStatus.READY
        assert _run(session, trading_day=TRADING_DAY).attempts == 1

    def test_any_user_watching_the_symbol_may_retry(self, session, watcher):
        """Production is idempotent per pair, so two people retrying is one
        run — there is nothing to gain by restricting it to whoever added it."""
        first = watcher(SYMBOL)
        second = watcher(SYMBOL)
        retry_analysis(session, first, SYMBOL, TRADING_DAY, failing_producer())

        outcome = retry_analysis(
            session, second, SYMBOL, TRADING_DAY, verdict_producer("hold")
        )

        assert outcome.status is RunStatus.READY
        assert _run(session).attempts == 2

    def test_a_user_not_watching_the_symbol_may_not_retry(self, session, watcher):
        stranger = watcher(OTHER)

        with pytest.raises(AnalysisRefusal) as refusal:
            retry_analysis(session, stranger, SYMBOL, TRADING_DAY, refuses_to_run)

        assert refusal.value.reason == "symbol_not_watched"

    def test_a_symbol_that_has_left_the_universe_produces_nothing(
        self, session, watcher, declared_universe
    ):
        """`unsupported` means no new Analysis is produced, and the retry button
        is the one path a user could use to argue otherwise."""
        user_id = watcher(SYMBOL)
        declared_universe(OTHER)

        with pytest.raises(AnalysisRefusal) as refusal:
            retry_analysis(session, user_id, SYMBOL, TRADING_DAY, refuses_to_run)

        assert refusal.value.reason == "not_in_universe"
        assert _analyses(session) == []


class TestStuckSweep:
    """A dead run must not hold a symbol hostage until someone notices."""

    def _producing_since(self, started_at: datetime) -> None:
        with get_sync_db() as session:
            session.add(
                AnalysisRun(
                    symbol=SYMBOL,
                    trading_day=TRADING_DAY,
                    status=RunStatus.PRODUCING.value,
                    origin=RunOrigin.NIGHTLY.value,
                    attempts=1,
                    started_at=started_at,
                )
            )

    def test_a_run_producing_past_the_window_is_failed(self, session):
        self._producing_since(NOW - timedelta(minutes=90))

        swept = sweep_stuck_runs(session, now=NOW, stuck_minutes=30)

        assert swept == 1
        run = _run(session)
        assert run.status == RunStatus.FAILED.value
        assert run.error_code == "run_abandoned"
        assert run.finished_at is not None

    def test_a_run_still_inside_the_window_is_left_alone(self, session):
        self._producing_since(NOW - timedelta(minutes=10))

        swept = sweep_stuck_runs(session, now=NOW, stuck_minutes=30)

        assert swept == 0
        assert _run(session).status == RunStatus.PRODUCING.value

    def test_a_ready_run_is_never_swept(self, session):
        produce_analysis(session, SYMBOL, TRADING_DAY, verdict_producer())

        assert sweep_stuck_runs(session, now=NOW + timedelta(days=7), stuck_minutes=1) == 0
        assert _run(session).status == RunStatus.READY.value

    def test_a_swept_run_can_be_retried_within_the_same_allowance(self, session, watcher):
        user_id = watcher(SYMBOL)
        self._producing_since(NOW - timedelta(minutes=90))
        sweep_stuck_runs(session, now=NOW, stuck_minutes=30)

        outcome = retry_analysis(
            session, user_id, SYMBOL, TRADING_DAY, verdict_producer("hold")
        )

        assert outcome.status is RunStatus.READY
        assert _run(session).attempts == 2

    def test_its_code_is_in_the_one_set_an_interface_branches_on(self):
        """The sweep's code sits outside the pipeline's taxonomy on purpose, so
        the set an interface renders from has to be the union — otherwise the
        first swept run shows as a blank."""
        assert ABANDONED_CODE not in FAILURE_CODES
        assert FAILURE_CODES < RUN_ERROR_CODES
        assert ABANDONED_CODE in RUN_ERROR_CODES

    def test_the_window_comes_from_configuration(self, session, monkeypatch):
        monkeypatch.setenv("ANALYSIS_RUN_STUCK_MINUTES", "5")
        get_settings.cache_clear()
        self._producing_since(NOW - timedelta(minutes=10))

        try:
            assert sweep_stuck_runs(session, now=NOW) == 1
        finally:
            monkeypatch.undo()
            get_settings.cache_clear()


class TestProducerSeam:
    """What A4 has to implement, and what it must not have to touch."""

    def test_the_producer_arrives_as_an_argument_rather_than_an_import(self, session):
        """A later milestone supplies its own producer and changes nothing in
        the state machine, which is the whole point of the seam."""
        seen: list[tuple[str, date]] = []

        def recording(symbol: str, trading_day: date) -> AnalysisDraft:
            seen.append((symbol, trading_day))
            return AnalysisDraft(verdict="watch", payload={})

        produce_analysis(session, SYMBOL, TRADING_DAY, recording)

        assert seen == [(SYMBOL, TRADING_DAY)]

    def test_the_stub_says_in_its_own_payload_that_it_is_a_stub(self, session):
        outcome = produce_analysis(session, SYMBOL, TRADING_DAY, stub_producer)

        assert outcome.analysis.payload["stub"] is True

    def test_a_production_failure_must_name_a_code_from_the_taxonomy(self):
        with pytest.raises(ValueError):
            ProductionFailure(code="something_went_wrong", message="nope")
