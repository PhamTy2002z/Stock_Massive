"""Durability, projection, checkpoint, spill, restart, and replay tests."""

from __future__ import annotations

import asyncio
import time
import tracemalloc
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.stocks.models import (
    RealtimeCheckpoint,
    RealtimeEvent,
    RealtimeHealth,
    RealtimeSpill,
)
from src.stocks.realtime import (
    AggressorSide,
    CanonicalUnits,
    DataHealthState,
    EventFamily,
    EventMetadata,
    Exchange,
    FeedHealthState,
    HealthTracker,
    HotProjectionStore,
    IngestionSpine,
    MarketDataSource,
    PriceUnit,
    ProductGroup,
    QualityState,
    QuantityUnit,
    RealtimeEventStore,
    TradeTick,
    TradingSession,
    ValueUnit,
    deserialize_event,
    serialize_event,
)


BASE_TIME = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)


def trade(sequence: int) -> TradeTick:
    provider_time = BASE_TIME + timedelta(milliseconds=sequence)
    return TradeTick(
        metadata=EventMetadata(
            source=MarketDataSource.DNSE,
            event_family=EventFamily.TRADE,
            symbol="FPT",
            exchange=Exchange.HOSE,
            board="G1",
            product_group=ProductGroup.EQUITY,
            trading_day=date(2026, 8, 24),
            session=TradingSession.CONTINUOUS,
            provider_time=provider_time,
            observed_time=provider_time + timedelta(milliseconds=1),
            units=CanonicalUnits(
                price=PriceUnit.VND,
                quantity=QuantityUnit.SHARE,
                value=ValueUnit.VND,
            ),
            schema_version=1,
            normalization_version=1,
            raw_payload_hash=f"{sequence + 1:064x}",
            quality_state=QualityState.VALID,
        ),
        price=Decimal("71400"),
        quantity=100,
        gross_trade_value_vnd=Decimal("7140000"),
        aggressor_side=AggressorSide.BUY,
        provider_trade_id=f"trade-{sequence}",
    )


@pytest.fixture
def event_store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            RealtimeEvent.__table__,
            RealtimeCheckpoint.__table__,
            RealtimeSpill.__table__,
            RealtimeHealth.__table__,
        ],
    )
    yield RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    engine.dispose()


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, **_kwargs):
        self.values[key] = value
        return True

    def eval(self, _script, *positional, **keyword):
        if keyword:
            keys = keyword["keys"]
            args = keyword["args"]
        else:
            key_count = positional[0]
            keys = positional[1 : 1 + key_count]
            args = positional[1 + key_count :]
        current = self.values.get(keys[0])
        if current is not None and current >= args[0]:
            return 0
        self.values[keys[0]] = args[0]
        self.values[keys[1]] = args[1]
        return 1


def test_normalized_event_round_trip_is_strict():
    original = trade(1)

    restored = deserialize_event(serialize_event(original))

    assert restored == original
    payload = serialize_event(original)
    payload["metadata"]["event_family"] = "unknown"
    with pytest.raises(ValueError, match="event family"):
        deserialize_event(payload)


@pytest.mark.asyncio
async def test_store_is_idempotent_and_replays_in_event_order(event_store):
    later, earlier = trade(2), trade(1)

    assert await event_store.append(later) is True
    assert await event_store.append(earlier) is True
    assert await event_store.append(earlier) is False

    replayed = await event_store.replay(date(2026, 8, 24), EventFamily.TRADE)
    assert replayed == (earlier, later)


@pytest.mark.asyncio
async def test_checkpoint_never_moves_backwards(event_store):
    later, earlier = trade(2), trade(1)

    saved = await event_store.save_checkpoint("consumer", later)
    unchanged = await event_store.save_checkpoint("consumer", earlier)
    loaded = await event_store.load_checkpoint(
        "consumer", "2026-08-24:trade"
    )

    assert unchanged.evidence_id == saved.evidence_id
    assert loaded and loaded.evidence_id == later.metadata.evidence_id


@pytest.mark.asyncio
async def test_spill_is_durable_and_duplicate_safe(event_store):
    event = trade(1)

    assert await event_store.spill(event, "queue_full") is True
    assert await event_store.spill(event, "queue_full") is False
    pending = await event_store.pending_spills()
    assert len(pending) == 1
    assert pending[0].event == event

    await event_store.mark_spill_recovered(pending[0].spill_id)
    assert await event_store.pending_spills() == ()


@pytest.mark.asyncio
async def test_retention_purges_expired_events_but_not_pending_spill(event_store):
    event = trade(1)
    assert await event_store.append(event)
    assert await event_store.spill(event, "queue_full")

    purged = await event_store.purge_expired(
        now=datetime(2028, 1, 1, tzinfo=UTC)
    )

    assert purged.events == 1
    assert purged.recovered_spills == 0
    assert await event_store.pending_spills()


@pytest.mark.asyncio
async def test_projection_rejects_older_delivery_and_exposes_health():
    redis = FakeRedis()
    projections = HotProjectionStore(redis)
    later, earlier = trade(2), trade(1)

    assert await projections.apply(later) is True
    assert await projections.apply(earlier) is False
    current = await projections.read(EventFamily.TRADE, "FPT", board="G1")
    assert current and current["evidence_id"] == later.metadata.evidence_id

    snapshot = HealthTracker(clock=lambda: BASE_TIME).feed(FeedHealthState.CONNECTED)
    await projections.save_health(snapshot)
    assert "stock:realtime:health:feed" in redis.values
    assert HotProjectionStore.key(
        EventFamily.SESSION, "MARKET", board="G1"
    ).endswith(":session:G1")


@pytest.mark.asyncio
async def test_restart_rebuild_is_deterministic_without_live_provider(event_store):
    redis = FakeRedis()
    first = IngestionSpine(event_store, HotProjectionStore(redis), queue_size=4)
    await first.start()
    await first.submit(trade(1))
    await first.submit(trade(2))
    await first.stop()

    replacement_redis = FakeRedis()
    restarted = IngestionSpine(
        event_store, HotProjectionStore(replacement_redis), queue_size=4
    )
    replayed = await restarted.replay_partition(
        date(2026, 8, 24), EventFamily.TRADE, rebuild_projection=True
    )

    assert replayed == (trade(1), trade(2))
    current = await HotProjectionStore(replacement_redis).read(
        EventFamily.TRADE, "FPT", board="G1"
    )
    assert current and current["evidence_id"] == trade(2).metadata.evidence_id


class BlockingStore:
    def __init__(self):
        self.release = asyncio.Event()
        self.entered = asyncio.Event()
        self.spilled = []
        self.health = {}

    async def append(self, event):
        self.entered.set()
        await self.release.wait()
        return True

    async def spill(self, event, reason):
        self.spilled.append((event, reason))
        return True

    async def pending_spills(self, _limit=1000):
        return ()

    async def mark_spill_recovered(self, _spill_id):
        raise AssertionError("no pending spills")

    async def save_checkpoint(self, consumer, event):
        return consumer, event

    async def save_health(self, snapshot):
        self.health[snapshot.scope] = snapshot


@pytest.mark.asyncio
async def test_bounded_queue_spills_before_acknowledging_pressure():
    store = BlockingStore()
    spine = IngestionSpine(store, HotProjectionStore(FakeRedis()), queue_size=1)
    await spine.start()
    await spine.submit(trade(1))
    await store.entered.wait()
    assert await spine.submit(trade(2)) is True

    assert await spine.submit(trade(3)) is False
    assert store.spilled == [(trade(3), "queue_full")]
    assert store.health["feed"].status == FeedHealthState.DEGRADED.value
    assert store.health["data"].status == DataHealthState.DEGRADED.value

    store.release.set()
    await spine.stop()


class LoadStore:
    def __init__(self):
        self.events = {}
        self.health = {}

    async def append(self, event):
        return self.events.setdefault(event.metadata.evidence_id, event) is event

    async def spill(self, event, reason):
        raise AssertionError(f"load envelope spilled: {reason} {event}")

    async def pending_spills(self, _limit=1000):
        return ()

    async def save_checkpoint(self, consumer, event):
        return consumer, event.metadata.evidence_id

    async def save_health(self, snapshot):
        self.health[snapshot.scope] = snapshot


@pytest.mark.asyncio
async def test_fixed_load_stays_inside_local_resource_envelope():
    """This is a deterministic engineering envelope, not a live-market SLO."""
    store = LoadStore()
    spine = IngestionSpine(
        store,
        HotProjectionStore(FakeRedis()),
        queue_size=128,
        worker_count=2,
    )
    tracemalloc.start()
    started = time.perf_counter()
    cpu_started = time.process_time()
    await spine.start()
    for sequence in range(2_000):
        while not await spine.submit(trade(sequence)):
            await asyncio.sleep(0)
        if sequence % 64 == 0:
            await asyncio.sleep(0)
    await spine.stop(timeout=10)
    elapsed = time.perf_counter() - started
    cpu_elapsed = time.process_time() - cpu_started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert len(store.events) == 2_000
    assert spine.queue_depth == 0
    assert elapsed < 10
    assert cpu_elapsed < 10
    assert peak < 32 * 1024 * 1024
