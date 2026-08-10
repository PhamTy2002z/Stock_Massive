"""Tests for the one-time history load from the Cover Source.

The history provider is injected and the database is SQLite in-memory, so a
whole load runs here without a network or a Postgres. What is under test is
what gets fetched, what does not get fetched twice, and what survives a
restart.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.backfill import Backfill, BackfillStateStore
from src.stocks.models import ProviderSnapshot, SymbolBackfill
from src.stocks.providers import (
    Capability,
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
    SnapshotStore,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import Universe

NOW = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)

# Small enough to read at a glance: the load reaches back ninety days, the Main
# Source covers the last thirty, and a call asks for thirty days at a time.
DEPTH_DAYS = 90
MAIN_SOURCE_DAYS = 30
CHUNK_DAYS = 30

# Where the Main Source takes over, and where the load therefore stops.
BOUNDARY = date(2026, 7, 11)
FIRST_SESSION = date(2026, 5, 12)


def history_snapshot(symbol: str, session_day: date) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=datetime.combine(
                session_day, datetime.min.time(), tzinfo=VN_TZ
            ),
            observed_at=NOW,
        ),
        last_price=21_850,
        volume=20_000_000,
    )


class FakeHistory:
    """Answers every window with one session dated at its last day."""

    source = ProviderSource.VNSTOCK

    def __init__(self, broken: set[str] | None = None):
        self.windows: list[tuple[str, date, date]] = []
        self.broken = broken or set()

    def fetch_market_history(self, symbol, from_date, to_date):
        self.windows.append((symbol, from_date, to_date))
        if symbol in self.broken:
            raise RuntimeError(f"vnstock market history fetch failed for {symbol}")
        return (history_snapshot(symbol, to_date),)

    def windows_for(self, symbol: str) -> list[tuple[date, date]]:
        return [(start, end) for asked, start, end in self.windows if asked == symbol]


def database():
    # One shared connection: the durable state is the point here, and the
    # default in-memory pool gives each connection a database of its own — so
    # a session opened on another thread would see an empty one.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ProviderSnapshot.__table__.create(engine)
    SymbolBackfill.__table__.create(engine)
    return engine


def backfill(engine, symbols=("HPG",), history=None, **overrides) -> Backfill:
    session = Session(engine)
    settings = {
        "now": lambda: NOW,
        "depth_days": DEPTH_DAYS,
        "main_source_days": MAIN_SOURCE_DAYS,
        "chunk_days": CHUNK_DAYS,
    }
    settings.update(overrides)
    return Backfill(
        store=SnapshotStore(session, redis=None),
        state=BackfillStateStore(session),
        universe=Universe(symbols=tuple(symbols)),
        history=history if history is not None else FakeHistory(),
        **settings,
    )


class TestFirstLoad:
    def test_a_new_symbol_is_loaded_up_to_where_the_main_source_takes_over(self):
        engine = database()
        history = FakeHistory()

        summary = backfill(engine, history=history).run()

        assert history.windows_for("HPG") == [
            (FIRST_SESSION, date(2026, 6, 10)),
            (date(2026, 6, 11), date(2026, 7, 10)),
            (date(2026, 7, 11), BOUNDARY),
        ]
        assert summary.completed == ("HPG",)
        assert summary.snapshots_written == 3

    def test_what_was_loaded_is_readable_as_the_cover_source(self):
        """The seam has to stay answerable: which stretch came from where is
        the question `docs/adr/0002` refuses to let the system lose."""
        engine = database()

        backfill(engine).run()

        with Session(engine) as session:
            store = SnapshotStore(session, redis=None)
            from_cover = store.latest(
                Capability.MARKET, "HPG", source=ProviderSource.VNSTOCK
            )
            from_main = store.latest(Capability.MARKET, "HPG")

        assert from_cover is not None
        assert from_cover.snapshot.metadata.source is ProviderSource.VNSTOCK
        # Nothing here pretends to be the Main Source, at the seam or anywhere.
        assert from_main is None


class TestRunningAgain:
    def test_a_loaded_symbol_is_never_loaded_again(self):
        """This is the most expensive thing asked of vnstock in the whole
        system, and the one thing that must not repeat."""
        engine = database()
        backfill(engine).run()

        history = FakeHistory()
        summary = backfill(engine, history=history).run()

        assert history.windows == []
        assert summary.completed == ("HPG",)
        assert summary.snapshots_written == 0

    def test_an_interrupted_load_resumes_where_it_stopped(self):
        """A restart mid-load must not mean paying for the whole stretch of
        history a second time."""
        engine = database()
        backfill(engine, history=FakeHistory(), symbols_per_run=1, chunk_limit=1).run()

        history = FakeHistory()
        backfill(engine, history=history).run()

        assert history.windows_for("HPG") == [
            (date(2026, 6, 11), date(2026, 7, 10)),
            (date(2026, 7, 11), BOUNDARY),
        ]

    def test_a_symbol_dropped_and_added_back_only_fetches_what_it_is_missing(self):
        engine = database()
        backfill(engine, symbols=("HPG",), chunk_limit=1).run()

        # The Universe changes underneath: HPG leaves, VCB arrives, HPG returns.
        backfill(engine, symbols=("VCB",)).run()
        history = FakeHistory()
        backfill(engine, symbols=("HPG", "VCB"), history=history).run()

        assert history.windows_for("VCB") == []
        assert history.windows_for("HPG") == [
            (date(2026, 6, 11), date(2026, 7, 10)),
            (date(2026, 7, 11), BOUNDARY),
        ]


class TestDurableState:
    def test_progress_survives_a_restart(self):
        """Held in the database rather than in memory, so nothing about the
        process staying up is load-bearing."""
        engine = database()
        backfill(engine, chunk_limit=1).run()

        with Session(engine) as session:
            (state,) = BackfillStateStore(session).all()

        assert state.symbol == "HPG"
        assert state.status == "in_progress"
        assert state.covered_through == date(2026, 6, 10)


class TestIsolationAndPacing:
    def test_one_symbol_failing_does_not_stop_the_others(self):
        engine = database()
        history = FakeHistory(broken={"HPG"})

        summary = backfill(engine, symbols=("HPG", "VCB"), history=history).run()

        assert summary.completed == ("VCB",)
        assert [failure.symbol for failure in summary.failed] == ["HPG"]
        assert "HPG" in summary.failed[0].reason

    def test_a_failed_symbol_keeps_the_ground_it_covered(self):
        """Its next run picks up from there rather than from the beginning."""
        engine = database()
        history = FakeHistory(broken={"HPG"})

        backfill(engine, history=history).run()

        with Session(engine) as session:
            (state,) = BackfillStateStore(session).all()
        assert state.status == "failed"
        assert state.covered_through is None

    def test_a_run_covers_only_so_many_symbols_before_leaving_the_rest(self):
        """The allowance is shared with the daily cycle, and a load that spent
        all of it would starve the collection everything else depends on."""
        engine = database()
        history = FakeHistory()

        summary = backfill(
            engine, symbols=("HPG", "VCB", "FPT"), history=history, symbols_per_run=2
        ).run()

        assert {symbol for symbol, _, _ in history.windows} == {"HPG", "VCB"}
        assert summary.completed == ("HPG", "VCB")


class TestTheOperatorsRoute:
    def test_progress_is_readable_per_symbol(self):
        """Which symbols are loaded, which are part-way and which failed spans
        many runs, so it is read from the durable state rather than from the
        last run's summary."""
        from fastapi.testclient import TestClient

        from src.core.database import get_sync_session
        from src.main import app

        engine = database()
        backfill(engine, symbols=("HPG", "VCB"), history=FakeHistory(broken={"VCB"})).run()

        session = Session(engine)
        app.dependency_overrides[get_sync_session] = lambda: session
        try:
            body = TestClient(app).get("/api/v1/jobs/backfill").json()
        finally:
            app.dependency_overrides.clear()
            session.close()

        by_symbol = {item["symbol"]: item for item in body}
        assert by_symbol["HPG"]["status"] == "completed"
        assert by_symbol["HPG"]["covered_through"] == BOUNDARY.isoformat()
        assert by_symbol["VCB"]["status"] == "failed"
        assert "VCB" in by_symbol["VCB"]["last_error"]

    @pytest.mark.asyncio
    async def test_the_load_is_scheduled_after_the_days_cycle(self):
        """The two share one vnstock allowance, and the daily cycle is the one
        users are waiting on that evening."""
        from unittest.mock import AsyncMock, patch

        from src.core.config import Settings
        from src.core.scheduler import setup_scheduler

        scheduler = AsyncMock()
        with patch(
            "src.core.scheduler.settings",
            Settings(
                scheduler_enabled=True,
                daily_ohlcv_enabled=False,
                financial_statements_enabled=False,
                sector_historical_enabled=False,
            ),
        ):
            await setup_scheduler(scheduler)

        registered = {
            call.kwargs.get("id"): call.args[1]
            for call in scheduler.add_schedule.await_args_list
        }
        assert (
            registered["universe-backfill"].hour > registered["universe-snapshots"].hour
        )


class TestNothingToDo:
    def test_an_empty_universe_is_a_valid_run_that_fetches_nothing(self):
        engine = database()
        history = FakeHistory()

        summary = backfill(engine, symbols=(), history=history).run()

        assert history.windows == []
        assert summary.snapshots_written == 0
        assert summary.completed == ()

    def test_a_symbol_whose_history_is_already_within_the_main_source_is_done(self):
        """Nothing sits deeper than the Main Source reaches, so there is no
        stretch for the Cover Source to load at all."""
        engine = database()
        history = FakeHistory()

        summary = backfill(engine, history=history, depth_days=MAIN_SOURCE_DAYS - 1).run()

        assert history.windows == []
        assert summary.completed == ("HPG",)
