"""Tests for PostgreSQL/Redis last-known-good snapshot behavior."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot
from src.stocks.providers import (
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
    SnapshotStore,
    ValuationSnapshot,
)


class MemoryRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, **kwargs):
        self.values[key] = value


class FailedRedis:
    def get(self, key):
        raise ConnectionError("redis unavailable")

    def set(self, key, value, **kwargs):
        raise ConnectionError("redis unavailable")


def snapshot_metadata(effective_at: datetime, observed_at: datetime) -> SnapshotMetadata:
    return SnapshotMetadata(
        source=ProviderSource.FIINQUANT,
        effective_at=effective_at,
        observed_at=observed_at,
    )


def market_snapshot(observed_at: datetime, symbol: str = "VCB") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        metadata=snapshot_metadata(observed_at, observed_at),
        last_price=59_700,
        volume=1_000,
    )


def test_save_is_idempotent_and_refreshes_redis():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    redis = MemoryRedis()

    with Session(engine) as session:
        store = SnapshotStore(session, redis=redis)
        snapshot = market_snapshot(datetime.now(timezone.utc))
        store.save(Capability.MARKET, snapshot)
        store.save(Capability.MARKET, snapshot)
        session.commit()

        count = session.scalar(select(func.count()).select_from(ProviderSnapshot))
        result = store.latest(Capability.MARKET, "vcb")

    assert count == 1
    assert result is not None
    assert result.snapshot == snapshot
    assert result.stale is False
    assert redis.values


def test_a_session_recollected_with_fuller_numbers_revises_the_row():
    """One session is one row, whatever the provider had filled in when.

    FiinQuant publishes the session that just closed before its active buy/sell
    split, so the next cycle re-reads the same session with more in it. Keyed by
    the session that write revises the row; keyed by anything finer — the tick
    the bar was stamped at, say — the fuller numbers would land beside the
    partial ones, and a reader taking the newest session would get the partial
    bar because its stamp is later in the day.
    """
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    session_start = datetime(2026, 8, 10, tzinfo=timezone.utc)

    with Session(engine) as session:
        store = SnapshotStore(session, redis=MemoryRedis())
        partial = market_snapshot(session_start).model_copy(
            update={"metadata": snapshot_metadata(session_start, session_start)}
        )
        store.save(Capability.MARKET, partial)
        store.save(
            Capability.MARKET,
            partial.model_copy(
                update={
                    "metadata": snapshot_metadata(
                        session_start,
                        session_start + timedelta(hours=9),
                    ),
                    "active_buy_volume": 8_727_000,
                    "active_sell_volume": 17_403_100,
                }
            ),
        )
        session.commit()

        count = session.scalar(select(func.count()).select_from(ProviderSnapshot))
        result = store.latest(Capability.MARKET, "VCB")

    assert count == 1
    assert result is not None
    assert result.snapshot.active_buy_volume == 8_727_000


def test_latest_falls_back_to_database_when_redis_is_unavailable():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    # Old enough to have missed several sessions, which is what the market
    # threshold measures now that collection runs once a session.
    observed_at = datetime.now(timezone.utc) - timedelta(days=10)

    with Session(engine) as session:
        SnapshotStore(session, redis=None).save(
            Capability.MARKET,
            market_snapshot(observed_at),
        )
        session.commit()

        result = SnapshotStore(session, redis=FailedRedis()).latest(
            Capability.MARKET,
            "VCB",
        )

    assert result is not None
    assert result.snapshot.last_price == 59_700
    assert result.stale is True
    assert result.age_seconds >= 10 * 24 * 60 * 60


def test_valuation_snapshots_round_trip_under_their_own_capability():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    observed_at = datetime.now(timezone.utc)
    valuation = ValuationSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=observed_at,
            observed_at=observed_at,
        ),
        provider_pe=12.5,
        provider_pb=1.8,
    )

    with Session(engine) as session:
        SnapshotStore(session, redis=None).save(Capability.VALUATION, valuation)
        SnapshotStore(session, redis=None).save(
            Capability.MARKET,
            market_snapshot(observed_at),
        )
        session.commit()

        # FailedRedis forces both reads through the PostgreSQL payload, so the
        # new capability is proven to survive the JSON round trip.
        store = SnapshotStore(session, redis=FailedRedis())
        read = store.latest(Capability.VALUATION, "vcb")
        market = store.latest(Capability.MARKET, "vcb")

    assert read is not None
    assert read.snapshot == valuation
    assert read.stale is False
    assert market is not None
    assert isinstance(market.snapshot, MarketSnapshot)


def test_save_rejects_a_snapshot_that_does_not_match_its_capability():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    observed_at = datetime.now(timezone.utc)

    with Session(engine) as session:
        store = SnapshotStore(session, redis=None)
        with pytest.raises(TypeError, match="valuation"):
            store.save(Capability.VALUATION, market_snapshot(observed_at))


def test_cover_source_snapshots_are_readable_only_when_asked_for_by_name():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    observed_at = datetime.now(timezone.utc)
    backfilled = MarketSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=observed_at,
            observed_at=observed_at,
        ),
        last_price=58_000,
    )

    with Session(engine) as session:
        store = SnapshotStore(session, redis=MemoryRedis())
        store.save(Capability.MARKET, backfilled)
        session.commit()

        # The main source holds nothing, and the store must not quietly serve
        # the cover source in its place: docs/adr/0002 rejected dynamic
        # fallback because the two sources disagree on units.
        assert store.latest(Capability.MARKET, "VCB") is None

        from_cover = store.latest(
            Capability.MARKET,
            "VCB",
            source=ProviderSource.VNSTOCK,
        )

    assert from_cover is not None
    assert from_cover.snapshot.last_price == 58_000


def test_store_rejects_a_source_that_does_not_own_the_capability():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    observed_at = datetime.now(timezone.utc)
    misattributed = FundamentalSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=observed_at,
            observed_at=observed_at,
        ),
        period_end=date(2026, 6, 30),
    )

    with Session(engine) as session:
        store = SnapshotStore(session, redis=None)

        with pytest.raises(ValueError, match="does not own"):
            store.latest(
                Capability.FUNDAMENTAL,
                "VCB",
                source=ProviderSource.FIINQUANT,
            )

        with pytest.raises(ValueError, match="does not own"):
            store.save(Capability.FUNDAMENTAL, misattributed)


def test_a_rejected_save_leaves_the_session_usable_for_the_next_one():
    """One snapshot the database refuses must not end the whole write.

    A failed flush leaves a SQLAlchemy session unusable until it is rolled
    back, so without a savepoint here the first rejected snapshot would take
    every later one in the same transaction with it — a collector cycle losing
    ninety-nine symbols because of one.
    """
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_halted BEFORE INSERT ON provider_snapshots "
            "WHEN NEW.symbol = 'HALT' "
            "BEGIN SELECT RAISE(ABORT, 'symbol is halted'); END"
        )
    observed_at = datetime.now(timezone.utc)

    with Session(engine) as session:
        store = SnapshotStore(session, redis=None)

        with pytest.raises(Exception):
            store.save(Capability.MARKET, market_snapshot(observed_at, symbol="HALT"))

        store.save(Capability.MARKET, market_snapshot(observed_at))
        session.commit()

        assert store.latest(Capability.MARKET, "VCB") is not None


def test_latest_returns_the_newest_session_not_the_newest_write():
    """A re-run over an older session must not displace the current one.

    Ordering by observed_at would: the second write is the later one, and the
    reader would be handed last week's close as though the market had moved
    backwards.
    """
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    now = datetime.now(timezone.utc)
    current = MarketSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=now - timedelta(hours=6),
            observed_at=now - timedelta(hours=5),
        ),
        last_price=59_700,
    )
    older_session_fetched_later = MarketSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=now - timedelta(days=7),
            observed_at=now,
        ),
        last_price=51_000,
    )

    with Session(engine) as session:
        store = SnapshotStore(session, redis=None)
        store.save(Capability.MARKET, current)
        store.save(Capability.MARKET, older_session_fetched_later)
        session.commit()

        result = store.latest(Capability.MARKET, "VCB")

    assert result is not None
    assert result.snapshot.last_price == 59_700


def test_latest_never_calls_a_secondary_provider_on_cache_miss():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)

    with Session(engine) as session:
        result = SnapshotStore(session, redis=MemoryRedis()).latest(
            Capability.MARKET,
            "FPT",
        )

    assert result is None
