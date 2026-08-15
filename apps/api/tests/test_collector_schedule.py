"""Tests for the scheduled and on-demand runs of the collection cycle.

The cycle itself is injected, so nothing here builds a provider, opens a
database session or reaches the network. What is under test is when the cycle
runs, what happens when it doesn't, and what an operator can see afterwards.
"""

import threading
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import Settings
from src.core.job_status_store import job_store
from src.stocks.collector import CollectionSummary, SymbolFailure
from src.stocks.collector_schedule import (
    CATCH_UP_CAPABILITIES,
    COLLECTOR_JOB_ID,
    WARMUP_JOB_ID,
    catch_up_market_data,
    collect_universe_snapshots,
    market_has_advanced_to,
    run_collection_cycle,
    run_symbol_warmup,
)
from src.stocks.providers import Capability
from src.stocks.warmup import WarmupResult, WarmupSummary

TRADING_DAY = date(2026, 8, 7)  # a Friday
CLOSED_DAY = date(2026, 8, 8)  # the Saturday after it


@pytest.fixture(autouse=True)
def forget_previous_runs():
    job_store.cleanup_old(max_age_hours=0)
    yield
    job_store.cleanup_old(max_age_hours=0)


def summary(written: int = 8) -> CollectionSummary:
    return CollectionSummary(
        snapshots_written=written,
        succeeded=("HPG", "VCB"),
        failures=(
            SymbolFailure(
                symbol="VCB",
                capability=Capability.VALUATION,
                reason="FiinQuant valuation fetch failed (SSLError)",
            ),
        ),
    )


def scheduler_settings(**overrides) -> Settings:
    """Settings with only the collection cycle scheduled, unless told otherwise."""
    return Settings(
        scheduler_enabled=True,
        sector_historical_enabled=False,
        **overrides,
    )


def one_schedule(scheduler, schedule_id: str):
    """Return the trigger registered under this id, or None if there is none."""
    for call in scheduler.add_schedule.await_args_list:
        if call.kwargs.get("id") == schedule_id:
            return call.args[1]
    return None


class RecordingCycle:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result if result is not None else summary()
        self.error = error
        self.runs = 0
        self.threads: list[int] = []

    def __call__(self) -> CollectionSummary:
        self.runs += 1
        self.threads.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        return self.result


class TestTradingDayGate:
    @pytest.mark.asyncio
    async def test_a_closed_exchange_is_not_worth_a_cycle(self):
        cycle = RecordingCycle()

        await collect_universe_snapshots(cycle=cycle, today=CLOSED_DAY)

        assert cycle.runs == 0

    @pytest.mark.asyncio
    async def test_a_trading_day_runs_the_cycle(self):
        cycle = RecordingCycle()

        await collect_universe_snapshots(cycle=cycle, today=TRADING_DAY)

        assert cycle.runs == 1

    @pytest.mark.asyncio
    async def test_an_on_demand_run_ignores_the_calendar(self):
        """Filling a gap after a bad day is exactly what this is for, and the
        day it is asked for is rarely the day the data is missing from."""
        cycle = RecordingCycle()

        await collect_universe_snapshots(
            force=True, cycle=cycle, today=CLOSED_DAY
        )

        assert cycle.runs == 1


class TestEventLoop:
    @pytest.mark.asyncio
    async def test_the_synchronous_cycle_runs_off_the_event_loop(self):
        """The cycle is synchronous and can take minutes. Run on the loop it
        would stop the API answering anything at all for that whole window."""
        cycle = RecordingCycle()

        await collect_universe_snapshots(cycle=cycle, today=TRADING_DAY)

        assert cycle.threads != [threading.get_ident()]


class TestOverlappingRuns:
    def test_a_second_run_is_refused_while_one_is_in_flight(self):
        """Two cycles writing at once spend the same allowance twice over for
        the same Snapshots, and the provider grants one connection anyway."""
        cycle = RecordingCycle()
        job_store.start_job(COLLECTOR_JOB_ID, "Thu thập Universe")

        result = run_collection_cycle(cycle=cycle)

        assert cycle.runs == 0
        assert result.status == "skipped"


class TestScheduling:
    @pytest.mark.asyncio
    async def test_the_cycle_is_scheduled_after_the_session_closes(self):
        from src.core.scheduler import setup_scheduler

        scheduler = AsyncMock()
        with patch("src.core.scheduler.settings", scheduler_settings()):
            await setup_scheduler(scheduler)

        trigger = one_schedule(scheduler, "universe-snapshots")
        # Well after the 15:00 close, and out of the way of the jobs that were
        # already scheduled: one worker, and one FiinQuant connection to share.
        assert (trigger.hour, trigger.minute) == (16, 15)

    @pytest.mark.asyncio
    async def test_the_cycle_can_be_turned_off_by_configuration(self):
        from src.core.scheduler import setup_scheduler

        scheduler = AsyncMock()
        with patch(
            "src.core.scheduler.settings", scheduler_settings(collector_enabled=False)
        ):
            await setup_scheduler(scheduler)

        assert one_schedule(scheduler, "universe-snapshots") is None


class TestTheOperatorsRoute:
    def test_the_last_run_is_readable_after_it_has_finished(self):
        from fastapi.testclient import TestClient

        from src.main import app

        run_collection_cycle(cycle=RecordingCycle())

        body = TestClient(app).get("/api/v1/jobs/collector").json()

        assert body["status"] == "completed"
        assert body["started_at"] is not None
        assert body["completed_at"] is not None
        assert body["result"]["snapshots_written"] == 8
        assert body["error"] is None

    def test_a_cycle_that_has_never_run_says_so_rather_than_inventing_one(self):
        from fastapi.testclient import TestClient

        from src.main import app

        response = TestClient(app).get("/api/v1/jobs/collector")

        assert response.status_code == 404

    def test_a_trigger_is_refused_while_a_cycle_is_in_flight(self):
        """The second run would spend the same allowance on the same Snapshots,
        and the operator should be told, not quietly given a no-op."""
        from fastapi.testclient import TestClient

        from src.auth.dependencies import require_admin
        from src.main import app

        app.dependency_overrides[require_admin] = lambda: None
        job_store.start_job(COLLECTOR_JOB_ID, "Thu thập Universe")
        try:
            response = TestClient(app).post("/api/v1/jobs/trigger/collector")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 409

    def test_a_trigger_is_refused_while_the_collector_is_switched_off(self):
        """Turning the collector off turns off every path that reaches a
        Provider Source, not only the scheduled one."""
        from fastapi.testclient import TestClient

        from src.auth.dependencies import require_admin
        from src.main import app

        app.dependency_overrides[require_admin] = lambda: None
        try:
            with patch(
                "src.stocks.jobs_router.get_settings",
                return_value=Settings(collector_enabled=False),
            ):
                response = TestClient(app).post("/api/v1/jobs/trigger/collector")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 409
        assert "COLLECTOR_ENABLED" in response.json()["detail"]


class TestLastRunIsVisible:
    def test_a_finished_run_reports_when_it_ran_and_what_it_wrote(self):
        cycle = RecordingCycle()

        run_collection_cycle(cycle=cycle)
        status = job_store.get_status(COLLECTOR_JOB_ID)

        assert status is not None
        assert status.status == "completed"
        assert status.started_at is not None
        assert status.completed_at is not None
        assert status.result["snapshots_written"] == 8
        assert status.result["succeeded"] == ["HPG", "VCB"]
        assert status.result["failures"] == [
            {
                "symbol": "VCB",
                "capability": "valuation",
                "reason": "FiinQuant valuation fetch failed (SSLError)",
            }
        ]

    def test_a_failed_cycle_reads_differently_from_one_that_wrote_nothing(self):
        """A cycle that failed on its first call and one that ran cleanly over
        an empty Universe both write nothing. A reader that cannot tell them
        apart reports a broken collector as a healthy one — including the
        scheduler's own log line."""
        failed = run_collection_cycle(cycle=RecordingCycle(error=RuntimeError("down")))
        job_store.cleanup_old(max_age_hours=0)
        empty = run_collection_cycle(cycle=RecordingCycle(result=summary(written=0)))

        assert (failed.status, empty.status) == ("failed", "completed")
        assert failed.snapshots_written == empty.snapshots_written == 0

    def test_a_failed_run_reports_the_reason_without_raising(self):
        """A scheduled job that raises takes the scheduler's thread with it.
        The reason belongs on the run's record, where someone can read it."""
        cycle = RecordingCycle(error=RuntimeError("FiinQuant login failed (SSLError)"))

        result = run_collection_cycle(cycle=cycle)
        status = job_store.get_status(COLLECTOR_JOB_ID)

        assert result.status == "failed"
        assert status is not None
        assert status.status == "failed"
        assert "SSLError" in status.error


class TestMarketCatchUp:
    """The late run that exists because a healthy cycle can still fall a day behind.

    FiinQuant appends the session that just closed late in the evening, so the
    16:15 cycle routinely comes away with yesterday's. Left alone that session
    is never collected: the next cycle asks for the one that just closed, and
    the deep Backfill never looks at recent history (``docs/adr/0005``).
    """

    @pytest.mark.asyncio
    async def test_a_day_the_store_already_holds_is_not_collected_again(self):
        cycle = RecordingCycle()

        outcome = await catch_up_market_data(
            cycle=cycle, today=TRADING_DAY, latest=lambda: TRADING_DAY
        )

        assert cycle.runs == 0
        assert outcome.status == "skipped"

    @pytest.mark.asyncio
    async def test_a_trading_day_the_store_never_reached_is_collected(self):
        cycle = RecordingCycle()

        outcome = await catch_up_market_data(
            cycle=cycle,
            today=TRADING_DAY,
            latest=lambda: date(2026, 8, 6),
        )

        assert cycle.runs == 1
        assert outcome.status == "completed"

    @pytest.mark.asyncio
    async def test_an_empty_store_is_collected_rather_than_read_as_up_to_date(self):
        cycle = RecordingCycle()

        await catch_up_market_data(
            cycle=cycle, today=TRADING_DAY, latest=lambda: None
        )

        assert cycle.runs == 1

    @pytest.mark.asyncio
    async def test_a_closed_exchange_is_not_worth_a_catch_up(self):
        cycle = RecordingCycle()

        await catch_up_market_data(
            cycle=cycle, today=CLOSED_DAY, latest=lambda: date(2026, 8, 6)
        )

        assert cycle.runs == 0

    def test_the_store_is_asked_rather_than_the_last_run_record(self):
        """A cycle that succeeded and wrote nothing is not a day collected.

        Reading the job record would call that done; reading the store sees the
        gap that is actually there.
        """
        assert market_has_advanced_to(TRADING_DAY, latest=lambda: TRADING_DAY)
        assert not market_has_advanced_to(TRADING_DAY, latest=lambda: date(2026, 8, 6))
        assert not market_has_advanced_to(TRADING_DAY, latest=lambda: None)

    def test_it_runs_under_the_collectors_own_guard(self):
        """The same work spending the same single FiinQuant connection."""
        cycle = RecordingCycle()
        job_store.start_job(COLLECTOR_JOB_ID, "Thu thập Universe")

        outcome = run_collection_cycle(cycle=cycle)

        assert cycle.runs == 0
        assert outcome.status == "skipped"

    @pytest.mark.asyncio
    async def test_the_three_conditional_re_runs_are_scheduled_in_ict(self):
        """One at each configured time, and each of them the same conditional call."""
        from src.core.scheduler import setup_scheduler

        scheduler = AsyncMock()
        with patch("src.core.scheduler.settings", scheduler_settings()):
            await setup_scheduler(scheduler)

        for schedule_id, expected in (
            ("market-catchup-1830", (18, 30)),
            ("market-catchup-2130", (21, 30)),
            ("market-catchup-2300", (23, 0)),
        ):
            trigger = one_schedule(scheduler, schedule_id)
            assert trigger is not None, schedule_id
            assert (trigger.hour, trigger.minute) == expected
            assert str(trigger.timezone) == "Asia/Ho_Chi_Minh"

    @pytest.mark.asyncio
    async def test_the_catch_up_can_be_turned_off_by_configuration(self):
        from src.core.scheduler import setup_scheduler

        scheduler = AsyncMock()
        with patch(
            "src.core.scheduler.settings",
            scheduler_settings(market_catchup_enabled=False),
        ):
            await setup_scheduler(scheduler)

        assert one_schedule(scheduler, "market-catchup-1830") is None
        assert one_schedule(scheduler, "market-catchup-2300") is None

    def test_the_times_are_parsed_where_a_wrong_one_can_still_be_seen(self):
        """A mistyped time explodes at configuration rather than vanishing."""
        assert scheduler_settings().market_catchup_schedule == (
            (18, 30),
            (21, 30),
            (23, 0),
        )
        with pytest.raises(ValueError):
            scheduler_settings(market_catchup_times="half past six").market_catchup_schedule


class TestWarmupRuns:
    def test_a_warm_up_is_guarded_apart_from_the_collection_cycle(self):
        """A cycle in flight must not stall a new cohort member for a day.

        The two are not the same work: a Warm-up reads a window of history for
        a handful of named symbols, a cycle reads one session for the whole
        Universe.
        """
        warmed: list[tuple[str, ...]] = []

        def warm(symbols):
            warmed.append(tuple(symbols))
            return WarmupSummary(
                results=(WarmupResult(symbol="FPT", status="completed", sessions_written=21),)
            )

        job_store.start_job(COLLECTOR_JOB_ID, "Thu thập Universe")
        outcome = run_symbol_warmup(["FPT"], warm=warm)

        assert warmed == [("FPT",)]
        assert outcome.status == "completed"
        assert outcome.sessions_written == 21

    def test_a_second_warm_up_is_refused_while_one_is_in_flight(self):
        job_store.start_job(WARMUP_JOB_ID, "Nạp cửa sổ tín hiệu")

        outcome = run_symbol_warmup(["FPT"], warm=lambda symbols: None)

        assert outcome.status == "skipped"

    def test_a_failed_warm_up_reports_the_reason_without_raising(self):
        def warm(symbols):
            raise ConnectionError("gateway unavailable")

        outcome = run_symbol_warmup(["FPT"], warm=warm)

        assert outcome.status == "failed"
        assert "ConnectionError" in outcome.error


class TestTheEveningCadence:
    """Three conditional re-runs, and what makes each of them conditional.

    The point of the evening's re-runs is *establishing* a Trading Day, not
    refreshing one already established. So every fire asks the store, and the
    one that finds a gap is the one that closes it (spec 0003 §11).
    """

    def test_only_the_two_fiinquant_capabilities_are_re_read(self):
        """The reference and fundamental capabilities have no part in this."""
        assert CATCH_UP_CAPABILITIES == (Capability.MARKET, Capability.VALUATION)

    @pytest.mark.asyncio
    async def test_the_re_runs_stop_as_soon_as_a_new_trading_day_exists(self):
        cycle = RecordingCycle()
        stored = [date(2026, 8, 6)]

        # 18:30 finds the gap and closes it.
        first = await catch_up_market_data(
            cycle=cycle, today=TRADING_DAY, latest=lambda: stored[0], capture=_no_cohort
        )
        stored[0] = TRADING_DAY

        # 21:30 and 23:00 find a day already established and do nothing.
        second = await catch_up_market_data(
            cycle=cycle, today=TRADING_DAY, latest=lambda: stored[0], capture=_no_cohort
        )
        third = await catch_up_market_data(
            cycle=cycle, today=TRADING_DAY, latest=lambda: stored[0], capture=_no_cohort
        )

        assert cycle.runs == 1
        assert (first.status, second.status, third.status) == (
            "completed",
            "skipped",
            "skipped",
        )

    @pytest.mark.asyncio
    async def test_a_restart_mid_evening_resumes_from_the_store(self):
        """Every input is Postgres or the clock; none of it is the job store.

        The in-memory job status store is empty after a restart, so a cadence
        that read it would treat a missed 18:30 as an evening that never needed
        one and wait until 21:30 to find out otherwise.
        """
        from src.core import scheduler

        job_store.cleanup_old(max_age_hours=0)
        with patch.object(scheduler, "settings", scheduler_settings()), patch.object(
            scheduler, "is_trading_day", lambda day: True
        ), patch.object(scheduler, "_time_passed_today", lambda hour, minute: True), patch(
            "src.stocks.collector_schedule.market_has_advanced_to",
            lambda day, latest=None: False,
        ):
            assert scheduler._should_catch_up_market_data() is True

        with patch.object(scheduler, "settings", scheduler_settings()), patch.object(
            scheduler, "is_trading_day", lambda day: True
        ), patch.object(scheduler, "_time_passed_today", lambda hour, minute: True), patch(
            "src.stocks.collector_schedule.market_has_advanced_to",
            lambda day, latest=None: True,
        ):
            assert scheduler._should_catch_up_market_data() is False


class TestCapturingTheCohort:
    """Establishing a Trading Day is what queues the evening's work."""

    @pytest.mark.asyncio
    async def test_a_completed_cycle_captures_the_cohort(self):
        captured: list[int] = []

        outcome = await collect_universe_snapshots(
            cycle=RecordingCycle(),
            today=TRADING_DAY,
            capture=lambda: captured.append(1) or {"created": ["FPT"]},
        )

        assert len(captured) == 1
        assert outcome.cohort == {"created": ["FPT"]}

    @pytest.mark.asyncio
    async def test_a_skipped_cycle_captures_nothing(self):
        """Nothing was written, so there is no day to have established."""
        captured: list[int] = []

        outcome = await collect_universe_snapshots(
            cycle=RecordingCycle(),
            today=CLOSED_DAY,
            capture=lambda: captured.append(1),
        )

        assert captured == []
        assert outcome.cohort is None

    @pytest.mark.asyncio
    async def test_a_failed_cycle_captures_nothing(self):
        captured: list[int] = []

        outcome = await collect_universe_snapshots(
            cycle=RecordingCycle(error=RuntimeError("FiinQuant said no")),
            today=TRADING_DAY,
            capture=lambda: captured.append(1),
        )

        assert outcome.status == "failed"
        assert captured == []

    @pytest.mark.asyncio
    async def test_the_catch_up_captures_it_too(self):
        """Whichever run establishes the day is the one that queues the evening."""
        captured: list[int] = []

        await catch_up_market_data(
            cycle=RecordingCycle(),
            today=TRADING_DAY,
            latest=lambda: date(2026, 8, 6),
            capture=lambda: captured.append(1),
        )

        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_a_capture_that_fails_does_not_take_the_collection_with_it(self):
        """The Snapshots are already committed; the next pass captures again."""
        from src.stocks import collector_schedule

        def explode(*args, **kwargs):
            raise RuntimeError("the database went away")

        # The real capture is used, and the session it opens is what fails —
        # patching the callable the schedule was handed would prove nothing.
        with patch("src.core.database.get_sync_db", explode):
            outcome = await collect_universe_snapshots(
                cycle=RecordingCycle(),
                today=TRADING_DAY,
                capture=collector_schedule.capture_nightly_cohort,
            )

        assert outcome.status == "completed"
        assert outcome.cohort is None


def _no_cohort() -> dict | None:
    return None
