"""Tests for one end-of-day collection cycle over the Universe.

Providers are injected, so nothing here patches a module and nothing reaches
the network. The store is the real one on SQLite in-memory, because what the
cycle is for is what ends up readable in it.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.stocks.collector import (
    VALUATION_LOOKBACK_DAYS,
    CollectionSummary,
    Collector,
    build_collector,
)
from src.stocks.models import CohortMember, CohortVersion, ProviderSnapshot
from src.stocks.providers.fiinquant import FiinQuantMarketProvider
from src.stocks.providers import (
    BatchTooLarge,
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    ProviderSource,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
    SnapshotStore,
    ValuationSnapshot,
)
from src.stocks.universe import Universe

NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)
SESSION_AT = datetime(2026, 8, 7, 0, 0, tzinfo=timezone.utc)


class MemoryRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, **kwargs):
        self.values[key] = value


def market_snapshot(symbol: str) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=SESSION_AT,
            observed_at=NOW,
        ),
        last_price=22_000,
        volume=1_000_000,
    )


def valuation_snapshot(symbol: str) -> ValuationSnapshot:
    return ValuationSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=SESSION_AT,
            observed_at=NOW,
        ),
        provider_pe=12.5,
        provider_pb=1.8,
    )


def reference_snapshot(symbol: str) -> ReferenceSnapshot:
    return ReferenceSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=SESSION_AT,
            observed_at=NOW,
        ),
        shares=(ShareCount(share_type=ShareType.LISTED, value=8_442_964_520),),
        current_foreign_room=2_299_133_934,
        total_foreign_room=4_137_052_614,
    )


def fundamental_snapshot(symbol: str) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol=symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=SESSION_AT,
            observed_at=NOW,
        ),
        period_end=date(2026, 6, 30),
        trailing_12_month_net_income_vnd=12_000_000_000_000,
        parent_equity_vnd=80_000_000_000_000,
    )


class FakeMarketProvider:
    source = ProviderSource.FIINQUANT

    def __init__(self):
        self.batches: list[list[str]] = []

    def fetch_market(self, symbols):
        self.batches.append(list(symbols))
        return tuple(market_snapshot(symbol) for symbol in symbols)


class GatewayBoundMarketProvider:
    """Times out on any batch above the size the gateway happens to tolerate."""

    source = ProviderSource.FIINQUANT

    def __init__(self, tolerated: int):
        self.tolerated = tolerated
        self.batches: list[list[str]] = []

    def fetch_market(self, symbols):
        self.batches.append(list(symbols))
        if len(symbols) > self.tolerated:
            raise BatchTooLarge("gateway timed out")
        return tuple(market_snapshot(symbol) for symbol in symbols)


class FakeValuationProvider:
    source = ProviderSource.FIINQUANT

    def __init__(self):
        self.windows: list[tuple[date, date]] = []

    def fetch_valuation(self, symbols, from_date, to_date):
        self.windows.append((from_date, to_date))
        return tuple(valuation_snapshot(symbol) for symbol in symbols)


class FakeReferenceProvider:
    source = ProviderSource.VNSTOCK

    def fetch_reference(self, symbols):
        return tuple(reference_snapshot(symbol) for symbol in symbols)


class FakeFundamentalProvider:
    source = ProviderSource.VNSTOCK

    def fetch_fundamentals(self, symbols):
        return tuple(fundamental_snapshot(symbol) for symbol in symbols)


def snapshot_store(redis=None) -> SnapshotStore:
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    # The Universe is half cohort now, and the cycle reads it off the session it
    # was handed, so the tables it lives in have to be there.
    CohortVersion.__table__.create(engine)
    CohortMember.__table__.create(engine)
    return SnapshotStore(Session(engine), redis=redis)


def collector(store: SnapshotStore, symbols=("HPG", "VCB"), **overrides) -> Collector:
    providers = {
        "market": FakeMarketProvider(),
        "valuation": FakeValuationProvider(),
        "reference": FakeReferenceProvider(),
        "fundamental": FakeFundamentalProvider(),
    }
    providers.update(overrides)
    return Collector(
        store=store,
        universe=Universe(explicit=tuple(symbols)),
        now=lambda: NOW,
        **providers,
    )


class TestOneCycle:
    def test_every_symbol_gets_a_snapshot_for_every_wired_capability(self):
        store = snapshot_store(redis=MemoryRedis())

        summary = collector(store).run()

        for capability in Capability:
            for symbol in ("HPG", "VCB"):
                read = store.latest(capability, symbol)
                assert read is not None, f"{symbol} has no {capability.value} snapshot"
        assert summary.snapshots_written == 8
        assert summary.succeeded == ("HPG", "VCB")
        assert summary.failures == ()

    def test_symbols_are_asked_for_in_batches_rather_than_one_at_a_time(self):
        """A batched call is worth ~5 seconds; the same symbols one at a time
        cost ~100. The cycle has to fit in the window after the session closes,
        so the batch size is the thing that decides whether it does."""
        market = FakeMarketProvider()
        symbols = [f"S{index:03d}" for index in range(60)]

        collector(snapshot_store(), symbols=symbols, market=market).run()

        assert [len(batch) for batch in market.batches] == [50, 10]


class TestGatewayTimeout:
    def test_a_timed_out_batch_is_halved_and_retried(self):
        market = GatewayBoundMarketProvider(tolerated=25)
        symbols = [f"S{index:03d}" for index in range(60)]
        store = snapshot_store()

        summary = collector(store, symbols=symbols, market=market).run()

        assert [len(batch) for batch in market.batches] == [50, 25, 25, 10]
        assert summary.failures == ()
        for symbol in symbols:
            assert store.latest(Capability.MARKET, symbol) is not None

    def test_a_batch_that_still_times_out_at_the_floor_is_a_failure(self):
        """Halving has an end. One symbol the gateway will not answer for is a
        failure recorded against that symbol, not a cycle that halves forever."""
        market = GatewayBoundMarketProvider(tolerated=0)
        store = snapshot_store()

        summary = collector(store, symbols=("HPG", "VCB"), market=market).run()

        assert [len(batch) for batch in market.batches] == [2, 1, 1]
        assert {failure.symbol for failure in summary.failures} == {"HPG", "VCB"}
        assert all(
            failure.capability is Capability.MARKET for failure in summary.failures
        )
        assert store.latest(Capability.MARKET, "HPG") is None


class TestIsolation:
    def test_one_broken_source_does_not_cost_the_other_sources_their_writes(self):
        """Losing valuation data must not also lose price data. Each capability
        comes from a source of its own (docs/adr/0002), and they fail apart."""

        class BrokenMarketProvider:
            source = ProviderSource.FIINQUANT

            def fetch_market(self, symbols):
                raise RuntimeError("FiinQuant market fetch failed (SSLError)")

        store = snapshot_store()

        summary = collector(store, market=BrokenMarketProvider()).run()

        assert store.latest(Capability.MARKET, "HPG") is None
        for capability in (
            Capability.VALUATION,
            Capability.REFERENCE,
            Capability.FUNDAMENTAL,
        ):
            assert store.latest(capability, "HPG") is not None
        assert summary.succeeded == ("HPG", "VCB")
        assert {failure.capability for failure in summary.failures} == {
            Capability.MARKET
        }

    def test_one_unusable_symbol_does_not_cost_the_batch_its_writes(self):
        """A halted or delisted ticker is a normal event in this market. It is
        recorded against that symbol and the rest of the batch carries on."""

        class PartialMarketProvider:
            source = ProviderSource.FIINQUANT

            def fetch_market(self, symbols):
                return tuple(
                    market_snapshot(symbol) for symbol in symbols if symbol != "HPG"
                )

        store = snapshot_store()

        summary = collector(store, market=PartialMarketProvider()).run()

        assert store.latest(Capability.MARKET, "VCB") is not None
        assert store.latest(Capability.MARKET, "HPG") is None
        assert summary.failures == ()
        assert [
            (missing.symbol, missing.capability) for missing in summary.missing
        ] == [("HPG", Capability.MARKET)]

    def test_a_snapshot_the_database_refuses_does_not_end_the_cycle(self):
        """A rejected write leaves a SQLAlchemy session unusable until it is
        rolled back, so one refused snapshot could otherwise take every later
        write in the cycle with it — every capability, every other symbol."""
        engine = create_engine("sqlite://")
        ProviderSnapshot.__table__.create(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TRIGGER reject_halted BEFORE INSERT ON provider_snapshots "
                "WHEN NEW.symbol = 'HPG' "
                "BEGIN SELECT RAISE(ABORT, 'symbol is halted'); END"
            )
        store = SnapshotStore(Session(engine), redis=None)

        summary = collector(store).run()

        for capability in Capability:
            assert store.latest(capability, "VCB") is not None
            assert store.latest(capability, "HPG") is None
        assert summary.succeeded == ("VCB",)
        assert {failure.symbol for failure in summary.failures} == {"HPG"}


class TestRunningAgain:
    def test_a_second_run_in_the_same_session_adds_no_second_snapshot(self):
        """Re-running after a partial failure is the operator's normal repair.
        It must cost nothing but the calls it makes."""
        store = snapshot_store()
        cycle = collector(store)

        first = cycle.run()
        second = cycle.run()
        rows = store.session.scalar(
            select(func.count()).select_from(ProviderSnapshot)
        )

        assert first.snapshots_written == 8
        assert second.snapshots_written == 8
        assert rows == 8


class TestDegradedInfrastructure:
    def test_a_broken_redis_does_not_stop_the_write_to_postgresql(self):
        """Redis is the fast current view, never the record. A cycle that lost
        its writes because a cache was down would be the tail wagging the dog."""

        class FailedRedis:
            def get(self, key):
                raise ConnectionError("redis unavailable")

            def set(self, key, value, **kwargs):
                raise ConnectionError("redis unavailable")

        store = snapshot_store(redis=FailedRedis())

        summary = collector(store).run()

        assert summary.snapshots_written == 8
        assert summary.failures == ()
        assert store.latest(Capability.MARKET, "HPG") is not None


class TestValuationWindow:
    def test_the_window_reaches_back_past_a_closed_exchange(self):
        """The ratio series is dated by session, so a cycle that only ever asked
        for today would lose the last session whenever it ran on a day the
        exchange was shut — and never go back for it. The window costs the same
        single call, and repeated sessions collapse in the store."""
        valuation = FakeValuationProvider()

        collector(snapshot_store(), valuation=valuation).run()

        assert valuation.windows == [
            (date(2026, 8, 7) - timedelta(days=VALUATION_LOOKBACK_DAYS), date(2026, 8, 7))
        ]


class TestErrorHygiene:
    def test_a_failed_login_never_reaches_the_summary_or_the_log(self, caplog):
        """A FiinQuant login failure has been seen to echo the credentials back.
        The cycle reports what the adapter chose to say and nothing else."""
        password = "s3cr3t-collector-password"

        def failing_login(username, password_arg):
            raise RuntimeError(f"login rejected for {username} / {password_arg}")

        provider = FiinQuantMarketProvider(
            username="collector@example.com",
            password=password,
            session_factory=failing_login,
        )

        with caplog.at_level(logging.WARNING):
            summary = collector(snapshot_store(), market=provider).run()

        reasons = " ".join(failure.reason for failure in summary.failures)
        assert "FiinQuant login failed" in reasons
        assert password not in reasons
        assert "collector@example.com" not in reasons
        assert password not in caplog.text
        assert "collector@example.com" not in caplog.text


class TestWiringFromConfiguration:
    def test_a_configured_account_wires_every_capability(self):
        built = build_collector(
            snapshot_store(),
            settings=Settings(
                universe_symbols="HPG,VCB",
                fiinquant_username="collector",
                fiinquant_password="password",
            ),
        )

        assert built.capabilities == tuple(Capability)

    def test_without_fiinquant_the_cycle_still_collects_what_vnstock_owns(self):
        """A development environment must start without a FiinQuant account, and
        collect the capabilities that do not need one rather than nothing."""
        built = build_collector(
            snapshot_store(),
            settings=Settings(
                universe_symbols="HPG",
                fiinquant_username="",
                fiinquant_password="",
            ),
        )

        assert built.capabilities == (Capability.REFERENCE, Capability.FUNDAMENTAL)


class TestEmptyUniverse:
    def test_an_empty_universe_is_a_valid_cycle_that_writes_nothing(self):
        """A fresh environment starts here, and it must not look broken."""
        market = FakeMarketProvider()
        store = snapshot_store()

        summary = collector(store, symbols=(), market=market).run()

        assert summary == CollectionSummary(
            snapshots_written=0, succeeded=(), failures=()
        )
        assert market.batches == []
