"""The one scheduled job the harness has, and the line that notices it stopped.

Two separate promises, and the second is the one that matters operationally:

**Nothing is scheduled unless somebody asked for it.** ``scheduler_enabled``
defaults to true, so a job registered unconditionally would start calling an
external provider on every machine that brings this stack up — 1,523 requests in
the market scope. The opt-in is a setting, and its default is off.

**A spine nobody is filling has to be loud.** The Trading Day calendar is derived
from ``bar_daily``, so when the fill stops nothing breaks: every answer keeps
citing a date and the date is quietly old. The expensive failure is not the job
failing, it is the job failing unnoticed.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from src.core import scheduler as scheduler_module
from src.core.config import get_settings
from src.stocks.trading_day import STALE_AFTER_DAYS, SpineFreshness


class _RecordingScheduler:
    """Captures what would have been scheduled, without a scheduler behind it."""

    def __init__(self) -> None:
        self.scheduled: list[dict] = []

    async def add_schedule(self, func, trigger, **kwargs):
        self.scheduled.append({"func": func, "trigger": trigger, **kwargs})
        return kwargs.get("id", "")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """The settings object is cached, and these tests change it."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestNothingIsScheduledUnlessAskedFor:
    @pytest.mark.asyncio
    async def test_the_backfill_is_absent_by_default(self, monkeypatch):
        monkeypatch.delenv("BACKFILL_DAILY_SCHEDULED", raising=False)
        get_settings.cache_clear()
        recording = _RecordingScheduler()

        await scheduler_module.setup_scheduler(recording)

        assert recording.scheduled == []

    @pytest.mark.asyncio
    async def test_the_default_is_off_in_the_settings_themselves(self, monkeypatch):
        """Asserted on the setting and not only on the effect.

        A future edit could register the job unconditionally and this file's
        other test would still pass if it only checked the scheduler when the
        flag was off.
        """
        monkeypatch.delenv("BACKFILL_DAILY_SCHEDULED", raising=False)
        get_settings.cache_clear()

        assert get_settings().backfill_daily_scheduled is False

    @pytest.mark.asyncio
    async def test_turning_it_on_schedules_one_job_after_the_close(self, monkeypatch):
        monkeypatch.setenv("BACKFILL_DAILY_SCHEDULED", "true")
        get_settings.cache_clear()
        recording = _RecordingScheduler()

        await scheduler_module.setup_scheduler(recording)

        assert len(recording.scheduled) == 1
        entry = recording.scheduled[0]
        assert entry["func"] is scheduler_module.fill_the_daily_spine
        assert entry["id"] == scheduler_module.BACKFILL_SCHEDULE_ID
        # 16:30 in Vietnam: the session closes at 15:00 and the ingest stamps its
        # own rows at 16:30 as "when a run that waited for the close would have
        # read it". The trigger and that stamp have to agree.
        assert entry["trigger"].hour == 16
        assert entry["trigger"].minute == 30
        # Vietnam time and not the container's: a UTC 16:30 would fire at 23:30
        # local, seven hours after the data settled.
        assert str(entry["trigger"].timezone) == "Asia/Ho_Chi_Minh"

    @pytest.mark.asyncio
    async def test_a_missed_run_is_made_up_once_and_not_twice(self, monkeypatch):
        """Two runs at once would spend the provider allowance twice over."""
        monkeypatch.setenv("BACKFILL_DAILY_SCHEDULED", "true")
        get_settings.cache_clear()
        recording = _RecordingScheduler()

        await scheduler_module.setup_scheduler(recording)
        entry = recording.scheduled[0]

        assert entry["coalesce"].name == "latest"
        # A restart shortly after the hour should still fill today, because the
        # spine is dated by session and a late run writes the same rows.
        assert entry["misfire_grace_time"] == timedelta(hours=2)


class TestTheScopesRunCheapestAndMostImportantFirst:
    def test_the_index_scope_leads(self):
        """VNINDEX is one call and it defines the Trading Day calendar.

        Ordered rather than incidental: without the calendar every window is
        anchored on the wrong session, so the cheapest scope is also the one that
        must not be behind 1,523 others.
        """
        assert scheduler_module.BACKFILL_SCOPES[0] == "index"
        assert scheduler_module.BACKFILL_SCOPES == ("index", "declared", "market")

    @pytest.mark.asyncio
    async def test_each_scope_runs_and_one_failing_does_not_stop_the_rest(
        self, monkeypatch, caplog
    ):
        """The market scope is the likeliest to fail and the least important."""
        ran: list[str] = []

        class _Report:
            attempted = 1
            skipped = 0
            rows_written = 5
            failures: tuple[str, ...] = ()

        def fake_run(*, scope: str):
            ran.append(scope)
            if scope == "declared":
                raise RuntimeError("provider refused this scope")
            return _Report()

        monkeypatch.setattr(
            "src.stocks.backfill_daily.run", fake_run, raising=True
        )

        with caplog.at_level(logging.ERROR):
            await scheduler_module.fill_the_daily_spine()

        assert ran == ["index", "declared", "market"]
        assert "declared" in caplog.text

    @pytest.mark.asyncio
    async def test_a_failing_scope_never_reaches_the_caller(self, monkeypatch):
        """A scheduled job that raises can take the process with it."""

        def always_raises(*, scope: str):
            raise RuntimeError("everything is broken")

        monkeypatch.setattr(
            "src.stocks.backfill_daily.run", always_raises, raising=True
        )

        # No pytest.raises: returning normally is the assertion.
        await scheduler_module.fill_the_daily_spine()


class TestAStaleSpineIsSaidOutLoud:
    def _freshness(self, *, age_days: int | None, latest: date | None) -> SpineFreshness:
        return SpineFreshness(
            latest_session=latest,
            last_observed_at=datetime(2026, 8, 21, 9, 30, tzinfo=timezone.utc),
            age_days=age_days,
        )

    @pytest.mark.asyncio
    async def test_a_current_spine_says_so_without_warning(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "src.main.spine_freshness",
            lambda session: self._freshness(age_days=1, latest=date(2026, 8, 20)),
        )
        import src.main as main_module

        with caplog.at_level(logging.WARNING):
            await main_module.report_spine_freshness_at_startup()

        assert caplog.records == []

    @pytest.mark.asyncio
    async def test_a_stale_spine_warns_and_names_the_command(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "src.main.spine_freshness",
            lambda session: self._freshness(
                age_days=STALE_AFTER_DAYS + 3, latest=date(2026, 8, 10)
            ),
        )
        import src.main as main_module

        with caplog.at_level(logging.WARNING):
            await main_module.report_spine_freshness_at_startup()

        assert caplog.records
        message = caplog.text
        # The reader of this line is an operator at startup, so it has to say
        # what to run rather than only that something is wrong.
        assert "backfill-daily" in message
        assert "old session rather than fail" in message

    @pytest.mark.asyncio
    async def test_an_empty_spine_warns_too(self, monkeypatch, caplog):
        """Never collected is not the same fact as gone stale, and both warn."""
        monkeypatch.setattr(
            "src.main.spine_freshness",
            lambda session: self._freshness(age_days=None, latest=None),
        )
        import src.main as main_module

        with caplog.at_level(logging.WARNING):
            await main_module.report_spine_freshness_at_startup()

        assert "holds no session at all" in caplog.text

    @pytest.mark.asyncio
    async def test_a_store_that_cannot_be_read_does_not_stop_startup(
        self, monkeypatch, caplog
    ):
        """An operational observation must not be able to keep the API down."""

        def explode(session):
            raise RuntimeError("the database is not there")

        monkeypatch.setattr("src.main.spine_freshness", explode)
        import src.main as main_module

        with caplog.at_level(logging.ERROR):
            await main_module.report_spine_freshness_at_startup()

        assert "freshness" in caplog.text
