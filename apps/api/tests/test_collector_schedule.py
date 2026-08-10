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
    COLLECTOR_JOB_ID,
    collect_universe_snapshots,
    run_collection_cycle,
)
from src.stocks.providers import Capability

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
        daily_ohlcv_enabled=False,
        financial_statements_enabled=False,
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
