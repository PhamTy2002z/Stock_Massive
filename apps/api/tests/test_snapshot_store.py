"""Tests for PostgreSQL/Redis last-known-good snapshot behavior."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot
from src.stocks.providers import (
    Capability,
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
    SnapshotStore,
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


def market_snapshot(observed_at: datetime) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=observed_at,
            observed_at=observed_at,
        ),
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


def test_latest_falls_back_to_database_when_redis_is_unavailable():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    observed_at = datetime.now(timezone.utc) - timedelta(minutes=6)

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
    assert result.age_seconds >= 360


def test_latest_never_calls_a_secondary_provider_on_cache_miss():
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)

    with Session(engine) as session:
        result = SnapshotStore(session, redis=MemoryRedis()).latest(
            Capability.MARKET,
            "FPT",
        )

    assert result is None
