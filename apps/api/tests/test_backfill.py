"""Tests for the one-time history load from the Cover Source.

The history provider is injected and the database is SQLite in-memory, so a
whole load runs here without a network or a Postgres. What is under test is
what gets fetched, what does not get fetched twice, and what survives a
restart.
"""

from datetime import date, datetime, timedelta, timezone

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.backfill import Backfill, BackfillStateStore, HistoryWindow
from src.stocks.models import ProviderSnapshot, SymbolBackfill
from src.stocks.providers import (
    Capability,
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
    SnapshotStore,
    ValuationSnapshot,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import Universe

NOW = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)

# Small enough to read at a glance: the load reaches back ninety days, the Main
# Source covers the last thirty, and a call asks for thirty days at a time.
DEPTH_DAYS = 90
MAIN_SOURCE_DAYS = 30
CHUNK_DAYS = 30

# A request reaches back before the chunk it covers, so the adapter can measure
# its first session against the one before it.
OVERLAP_DAYS = 7

# Where the Main Source takes over, and where the load therefore stops.
BOUNDARY = date(2026, 7, 11)
FIRST_SESSION = date(2026, 5, 12)


def asked(covered_from: date, covered_to: date) -> tuple[date, date]:
    """The window a chunk covering these days actually requests."""
    return covered_from - timedelta(days=OVERLAP_DAYS), covered_to


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


def main_session(symbol: str, session_day: date) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=datetime.combine(
                session_day, datetime.min.time(), tzinfo=VN_TZ
            ),
            observed_at=NOW,
        ),
        last_price=22_000,
        volume=28_000_000,
    )


def valuation_session(symbol: str, session_day: date) -> ValuationSnapshot:
    return ValuationSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=datetime.combine(
                session_day, datetime.min.time(), tzinfo=VN_TZ
            ),
            observed_at=NOW,
        ),
        provider_pe=12.86,
        provider_pb=1.61,
    )


class FakeMainHistory:
    """The Main Source answering for its own window, one session per request."""

    source = ProviderSource.FIINQUANT

    def __init__(self, broken: set[str] | None = None):
        self.windows: list[tuple[str, date, date]] = []
        self.broken = broken or set()

    def fetch_market_history(self, symbol, from_date, to_date):
        self.windows.append((symbol, from_date, to_date))
        if symbol in self.broken:
            raise RuntimeError(f"FiinQuant market history fetch failed for {symbol}")
        return (main_session(symbol, to_date),)

    def windows_for(self, symbol: str) -> list[tuple[date, date]]:
        return [(start, end) for asked, start, end in self.windows if asked == symbol]


class FakeValuationHistory:
    def __init__(self, broken: set[str] | None = None):
        self.windows: list[tuple[tuple[str, ...], date, date]] = []
        self.broken = broken or set()

    def fetch_valuation(self, symbols, from_date, to_date):
        self.windows.append((tuple(symbols), from_date, to_date))
        if set(symbols) & self.broken:
            raise RuntimeError("FiinQuant valuation fetch failed")
        return tuple(valuation_session(symbol, to_date) for symbol in symbols)


class KilledMidLoad(BaseException):
    """Stands in for the process going away part-way through a run.

    A BaseException on purpose: it sails past the per-symbol handling the same
    way a real kill would, so what is left behind is what a restart would find.
    """


class FakeHistory:
    """Answers every window with one session dated at its last day."""

    source = ProviderSource.VNSTOCK

    def __init__(
        self,
        broken: set[str] | None = None,
        die_after: int | None = None,
        unlisted_before: date | None = None,
    ):
        self.windows: list[tuple[str, date, date]] = []
        self.broken = broken or set()
        self.die_after = die_after
        self.unlisted_before = unlisted_before

    def fetch_market_history(self, symbol, from_date, to_date):
        if self.die_after is not None and len(self.windows) >= self.die_after:
            raise KilledMidLoad()
        self.windows.append((symbol, from_date, to_date))
        if symbol in self.broken:
            raise RuntimeError(f"vnstock market history fetch failed for {symbol}")
        if self.unlisted_before is not None and to_date < self.unlisted_before:
            # What vnstock does for a window before the company listed: it
            # raises rather than answering with no sessions.
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
        "window": HistoryWindow(
            depth_days=DEPTH_DAYS,
            main_source_days=MAIN_SOURCE_DAYS,
            chunk_days=CHUNK_DAYS,
        ),
    }
    settings.update(overrides)
    return Backfill(
        store=SnapshotStore(session, redis=None),
        # The state store keeps the run's clock: the backoff it writes is read
        # back by the next run's selection, and two clocks would let a symbol
        # come out of a backoff it never served.
        state=BackfillStateStore(session, now=settings["now"]),
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
            asked(FIRST_SESSION, date(2026, 6, 10)),
            asked(date(2026, 6, 11), date(2026, 7, 10)),
            asked(date(2026, 7, 11), BOUNDARY),
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


class TestTheSeamBetweenSources:
    def test_overlapping_chunks_leave_one_snapshot_per_session(self):
        """Each request reaches back before the chunk it covers, so sessions
        arrive twice. Twice-written must still mean once-stored."""
        engine = database()

        backfill(engine).run()
        backfill(engine, symbols=("HPG",)).run()

        with Session(engine) as session:
            rows = session.scalar(select(func.count()).select_from(ProviderSnapshot))
            sessions = session.scalars(
                select(ProviderSnapshot.effective_at).distinct()
            ).all()

        assert rows == len(sessions)

    def test_the_same_session_from_both_sources_is_two_answerable_snapshots(self):
        """The two disagree on how much of a session they describe, so neither
        overwrites the other — and each stays traceable to what produced it."""
        engine = database()
        backfill(engine).run()

        with Session(engine) as session:
            store = SnapshotStore(session, redis=None)
            store.save(
                Capability.MARKET,
                MarketSnapshot(
                    symbol="HPG",
                    metadata=SnapshotMetadata(
                        source=ProviderSource.FIINQUANT,
                        effective_at=datetime.combine(
                            BOUNDARY, datetime.min.time(), tzinfo=VN_TZ
                        ),
                        observed_at=NOW,
                    ),
                    last_price=22_000,
                ),
            )
            session.commit()

            from_main = store.latest(Capability.MARKET, "HPG")
            from_cover = store.latest(
                Capability.MARKET, "HPG", source=ProviderSource.VNSTOCK
            )

        assert from_main is not None and from_main.snapshot.last_price == 22_000
        assert from_cover is not None and from_cover.snapshot.last_price == 21_850


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
        with pytest.raises(KilledMidLoad):
            backfill(engine, history=FakeHistory(die_after=1)).run()

        history = FakeHistory()
        backfill(engine, history=history).run()

        assert history.windows_for("HPG") == [
            asked(date(2026, 6, 11), date(2026, 7, 10)),
            asked(date(2026, 7, 11), BOUNDARY),
        ]

    def test_a_symbol_dropped_and_added_back_only_fetches_what_it_is_missing(self):
        engine = database()
        with pytest.raises(KilledMidLoad):
            backfill(engine, symbols=("HPG",), history=FakeHistory(die_after=1)).run()

        # The Universe changes underneath: HPG leaves, VCB arrives, HPG returns.
        backfill(engine, symbols=("VCB",)).run()
        history = FakeHistory()
        backfill(engine, symbols=("HPG", "VCB"), history=history).run()

        assert history.windows_for("VCB") == []
        assert history.windows_for("HPG") == [
            asked(date(2026, 6, 11), date(2026, 7, 10)),
            asked(date(2026, 7, 11), BOUNDARY),
        ]


class TestDurableState:
    def test_progress_survives_a_restart(self):
        """Held in the database rather than in memory, so nothing about the
        process staying up is load-bearing."""
        engine = database()
        with pytest.raises(KilledMidLoad):
            backfill(engine, history=FakeHistory(die_after=1)).run()

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
            with patch(
                "src.stocks.jobs_router.get_universe",
                return_value=Universe(symbols=("HPG", "VCB", "FPT")),
            ):
                body = TestClient(app).get("/api/v1/jobs/backfill").json()
        finally:
            app.dependency_overrides.clear()
            session.close()

        by_symbol = {item["symbol"]: item for item in body}
        assert by_symbol["HPG"]["status"] == "completed"
        assert by_symbol["HPG"]["covered_through"] == BOUNDARY.isoformat()
        assert by_symbol["VCB"]["status"] == "failed"
        assert "VCB" in by_symbol["VCB"]["last_error"]
        # A symbol the load has not reached is reported rather than missing.
        assert by_symbol["FPT"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_the_load_is_scheduled_after_the_days_cycle(self):
        """The two share one vnstock allowance, and the daily cycle is the one
        users are waiting on that evening."""
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
                backfill_enabled=True,
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

        summary = backfill(
            engine,
            history=history,
            window=HistoryWindow(
                depth_days=MAIN_SOURCE_DAYS - 1,
                main_source_days=MAIN_SOURCE_DAYS,
                chunk_days=CHUNK_DAYS,
            ),
        ).run()

        assert history.windows == []
        assert summary.completed == ("HPG",)


# Where the Main Source's own window begins, and where the load now ends.
MAIN_SEGMENT_START = date(2026, 7, 12)
TODAY = date(2026, 8, 10)


class TestTheMainSourceWindow:
    """The stretch the Main Source is granted but nothing had ever fetched.

    Backfill loaded only what was deeper than the Main Source's reach, and the
    daily cycle writes one session at a time from today — so between them sat
    five years no read would ever cover, and a chart drawn from the store had a
    hole in exactly the range a reader looks at most.
    """

    def test_each_stretch_is_asked_of_the_source_that_reaches_it(self):
        engine = database()
        cover, main = FakeHistory(), FakeMainHistory()

        summary = backfill(engine, history=cover, main_history=main).run()

        assert cover.windows_for("HPG") == [
            asked(FIRST_SESSION, date(2026, 6, 10)),
            asked(date(2026, 6, 11), date(2026, 7, 10)),
            asked(date(2026, 7, 11), BOUNDARY),
        ]
        assert main.windows_for("HPG") == [asked(MAIN_SEGMENT_START, TODAY)]
        assert summary.completed == ("HPG",)

    def test_each_session_keeps_the_source_that_answered_for_it(self):
        engine = database()

        backfill(engine, history=FakeHistory(), main_history=FakeMainHistory()).run()

        with Session(engine) as session:
            series = SnapshotStore(session, redis=None).series(
                Capability.MARKET, "HPG", now=NOW
            )

        sources = [snapshot.metadata.source for snapshot in series.snapshots]
        assert sources[0] is ProviderSource.VNSTOCK
        assert sources[-1] is ProviderSource.FIINQUANT

    def test_without_a_main_source_the_load_still_stops_where_it_always_did(self):
        """A development environment has no FiinQuant account and must not sit
        forever half-loaded waiting for a window nothing can fetch."""
        engine = database()

        summary = backfill(engine, history=FakeHistory()).run()

        assert summary.completed == ("HPG",)

    def test_the_main_window_is_loaded_once_an_account_appears(self):
        """A symbol completed without an account is owed the window again."""
        engine = database()
        backfill(engine, history=FakeHistory()).run()

        main = FakeMainHistory()
        summary = backfill(engine, history=FakeHistory(), main_history=main).run()

        assert main.windows_for("HPG") == [asked(MAIN_SEGMENT_START, TODAY)]
        assert summary.completed == ("HPG",)

    def test_the_ratio_series_is_loaded_across_the_same_window(self):
        """Story 7 of #6 wants P/E and P/B over time, and the Collector's weekly
        look-back only ever builds that going forward."""
        engine = database()
        valuation = FakeValuationHistory()

        backfill(
            engine,
            history=FakeHistory(),
            main_history=FakeMainHistory(),
            valuation_history=valuation,
        ).run()

        assert valuation.windows == [(("HPG",), *asked(MAIN_SEGMENT_START, TODAY))]
        with Session(engine) as session:
            series = SnapshotStore(session, redis=None).series(
                Capability.VALUATION, "HPG", now=NOW
            )
        assert len(series.snapshots) == 1

    def test_a_loaded_symbol_is_not_asked_again_the_next_day(self):
        """The one-time load stays one-time. Every session after the walk is
        the Collector's, and re-fetching them daily would be a second cycle
        writing what the first already wrote."""
        engine = database()
        backfill(engine, history=FakeHistory(), main_history=FakeMainHistory()).run()

        tomorrow = NOW + timedelta(days=1)
        cover, main = FakeHistory(), FakeMainHistory()
        summary = backfill(
            engine,
            history=cover,
            main_history=main,
            now=lambda: tomorrow,
        ).run()

        assert cover.windows == []
        assert main.windows == []
        assert summary.snapshots_written == 0
        assert summary.completed == ("HPG",)

    def test_a_company_younger_than_the_depth_loads_from_its_first_session(self):
        """vnstock raises for a window before the symbol listed.

        TCB listed in 2018 and the load reaches back a decade, so its first
        chunks can never be answered — and a symbol whose walk stops on the
        first refusal never loads the years it does have. Measured against the
        live provider, not guessed.
        """
        engine = database()
        history = FakeHistory(unlisted_before=date(2026, 6, 11))

        summary = backfill(engine, history=history).run()

        # Every chunk was still attempted: nothing here knows a listing date.
        assert len(history.windows_for("HPG")) == 3
        assert summary.completed == ("HPG",)
        with Session(engine) as session:
            stored = SnapshotStore(session, redis=None).series(
                Capability.MARKET, "HPG", now=NOW
            )
        assert len(stored.snapshots) == 2

    def test_a_symbol_that_answers_nothing_at_all_is_not_marked_loaded(self):
        """An outage on a first run must not settle a symbol with no history."""
        engine = database()

        summary = backfill(engine, history=FakeHistory(broken={"HPG"})).run()

        assert summary.completed == ()
        assert summary.failed[0].symbol == "HPG"

    def test_the_ratio_series_is_not_asked_of_the_cover_stretch(self):
        """vnstock owns no ratio series, and the deep years are its stretch."""
        engine = database()
        valuation = FakeValuationHistory()

        backfill(engine, history=FakeHistory(), valuation_history=valuation).run()

        assert valuation.windows == []


class TestFairRotation:
    """A run has a handful of slots, and a broken symbol must not own them all.

    In Universe order the first symbols take every slot of every run, so a
    symbol that fails on its first chunk is retried tonight, tomorrow and the
    night after while the symbols behind it are never reached at all
    (``docs/adr/0005``).
    """

    universe = ("AAA", "BBB", "CCC")

    def state_for(self, engine, symbol: str) -> SymbolBackfill:
        with Session(engine) as session:
            return BackfillStateStore(session).get(symbol)

    def test_a_failing_symbol_frees_the_slot_for_the_ones_behind_it(self):
        engine = database()
        history = FakeHistory(broken={"AAA"})

        def run_once() -> set[str]:
            """Which symbols this run actually spent its slot on."""
            before = len(history.windows)
            backfill(
                engine, symbols=self.universe, history=history, symbols_per_run=1
            ).run()
            return {symbol for symbol, _, _ in history.windows[before:]}

        assert run_once() == {"AAA"}
        # AAA is in its backoff now, so the slot goes to the symbol behind it
        # rather than being spent on the same failure a second night running.
        assert run_once() == {"BBB"}
        assert run_once() == {"CCC"}

    def test_a_symbol_inside_its_backoff_is_not_asked_again(self):
        engine = database()
        history = FakeHistory(broken={"AAA"})

        backfill(engine, symbols=("AAA",), history=history, symbols_per_run=1).run()
        asked_once = len(history.windows_for("AAA"))
        backfill(engine, symbols=("AAA",), history=history, symbols_per_run=1).run()

        assert len(history.windows_for("AAA")) == asked_once

    def test_the_backoff_widens_with_each_failure_in_a_row(self):
        engine = database()
        history = FakeHistory(broken={"AAA"})
        clock = NOW

        for _ in range(3):
            backfill(
                engine,
                symbols=("AAA",),
                history=history,
                symbols_per_run=1,
                now=lambda captured=clock: captured,
            ).run()
            # Far enough past the backoff that the next run takes it on again.
            clock += timedelta(days=14)

        state = self.state_for(engine, "AAA")
        assert state.attempts == 3
        assert state.next_attempt_at is not None

    def test_a_symbol_out_of_its_backoff_comes_back_into_the_rotation(self):
        engine = database()
        history = FakeHistory(broken={"AAA"})

        backfill(engine, symbols=("AAA",), history=history, symbols_per_run=1).run()
        asked_once = len(history.windows_for("AAA"))
        backfill(
            engine,
            symbols=("AAA",),
            history=history,
            symbols_per_run=1,
            now=lambda: NOW + timedelta(days=14),
        ).run()

        assert len(history.windows_for("AAA")) > asked_once

    def test_progress_clears_the_backoff_rather_than_a_clean_run(self):
        """A walk that got one chunk further is a walk that is working.

        Making it serve out a penalty earned by an earlier failure would stall a
        symbol that is only slow.
        """
        engine = database()
        backfill(
            engine, symbols=("AAA",), history=FakeHistory(broken={"AAA"}), symbols_per_run=1
        ).run()
        assert self.state_for(engine, "AAA").attempts == 1

        backfill(
            engine,
            symbols=("AAA",),
            history=FakeHistory(),
            symbols_per_run=1,
            now=lambda: NOW + timedelta(days=14),
        ).run()

        state = self.state_for(engine, "AAA")
        assert state.attempts == 0
        assert state.next_attempt_at is None
