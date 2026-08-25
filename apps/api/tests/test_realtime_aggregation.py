"""Deterministic trade-derived bars for the S3 realtime slice."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.stocks.models import RealtimeEvent
from src.stocks.realtime.aggregation import aggregate_bars_to_daily, aggregate_trades
from src.stocks.realtime.bar_projection import TradeBarProjector
from src.stocks.realtime.contracts import (
    AggressorSide,
    BarResolution,
    CanonicalUnits,
    EventFamily,
    EventMetadata,
    Exchange,
    MarketDataSource,
    PriceUnit,
    ProductGroup,
    QualityState,
    QuantityUnit,
    TradeTick,
    TradingSession,
    ValueUnit,
    ClosedBar,
)
from src.stocks.realtime.projections import HotProjectionStore
from src.stocks.realtime.storage import RealtimeEventStore

from .test_realtime_ingestion import FakeRedis


BASE = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)


def trade(
    sequence: int,
    *,
    minute: int = 0,
    second: int = 0,
    board: str = "G1",
    session: TradingSession = TradingSession.CONTINUOUS,
    price: str = "71400",
    quantity: int = 100,
) -> TradeTick:
    provider_time = BASE + timedelta(minutes=minute, seconds=second)
    return TradeTick(
        metadata=EventMetadata(
            source=MarketDataSource.DNSE,
            event_family=EventFamily.TRADE,
            symbol="FPT",
            exchange=Exchange.HOSE,
            board=board,
            product_group=ProductGroup.EQUITY,
            trading_day=date(2026, 8, 24),
            session=session,
            provider_time=provider_time,
            observed_time=provider_time + timedelta(milliseconds=sequence),
            units=CanonicalUnits(
                price=PriceUnit.VND,
                quantity=QuantityUnit.SHARE,
                value=ValueUnit.VND,
            ),
            schema_version=1,
            normalization_version=1,
            raw_payload_hash=f"{sequence:064x}",
            quality_state=QualityState.VALID,
        ),
        price=Decimal(price),
        quantity=quantity,
        gross_trade_value_vnd=Decimal(price) * quantity,
        aggressor_side=AggressorSide.BUY,
        provider_trade_id=f"trade-{sequence}",
    )


def test_round_lot_and_odd_lot_boards_never_merge():
    bars = aggregate_trades((trade(1, board="G1"), trade(2, board="G4", quantity=7)))

    assert [(bar.metadata.board, bar.volume) for bar in bars] == [
        ("G1", 100),
        ("G4", 7),
    ]


def test_reordered_and_duplicate_delivery_produces_the_same_bar():
    first = trade(1, second=1, price="71000")
    last = trade(2, second=30, price="72000", quantity=200)

    ordered = aggregate_trades((first, last))
    replayed = aggregate_trades((last, first, first))

    assert replayed == ordered
    bar = ordered[0]
    assert (bar.open_price, bar.high_price, bar.low_price, bar.close_price) == (
        Decimal("71000"),
        Decimal("72000"),
        Decimal("71000"),
        Decimal("72000"),
    )
    assert bar.volume == 300
    assert bar.total_value_vnd == Decimal("21500000")
    assert bar.input_evidence_ids == (
        first.metadata.evidence_id,
        last.metadata.evidence_id,
    )


def test_session_identity_prevents_a_bar_crossing_a_boundary():
    bars = aggregate_trades(
        (
            trade(1, session=TradingSession.ATO),
            trade(2, session=TradingSession.CONTINUOUS),
        )
    )

    assert [bar.metadata.session for bar in bars] == [
        TradingSession.ATO,
        TradingSession.CONTINUOUS,
    ]


def test_accepted_higher_resolution_retains_method_and_evidence():
    inputs = (trade(1, minute=0), trade(2, minute=1), trade(3, minute=2))

    bars = aggregate_trades(
        inputs,
        resolutions=(BarResolution.MINUTE_1, BarResolution.MINUTE_3),
    )

    minute_bars = [bar for bar in bars if bar.resolution is BarResolution.MINUTE_1]
    higher = [bar for bar in bars if bar.resolution is BarResolution.MINUTE_3]
    assert len(minute_bars) == 3
    assert len(higher) == 1
    assert higher[0].volume == 300
    assert higher[0].method_version == 1
    assert higher[0].metadata.source is MarketDataSource.INTERNAL
    assert higher[0].input_evidence_ids == tuple(
        item.metadata.evidence_id for item in inputs
    )


@pytest.mark.asyncio
async def test_hot_bar_projection_keeps_board_and_resolution_in_identity():
    bars = aggregate_trades(
        (trade(1, minute=0), trade(2, minute=1), trade(3, minute=2)),
        resolutions=(BarResolution.MINUTE_1, BarResolution.MINUTE_3),
    )
    redis = FakeRedis()
    projections = HotProjectionStore(redis)
    for bar in bars:
        await projections.apply(bar)

    one_minute = await projections.read(
        EventFamily.CLOSED_BAR,
        "FPT",
        board="G1",
        resolution=BarResolution.MINUTE_1.value,
    )
    three_minute = await projections.read(
        EventFamily.CLOSED_BAR,
        "FPT",
        board="G1",
        resolution=BarResolution.MINUTE_3.value,
    )

    assert one_minute is not None
    assert three_minute is not None
    assert one_minute["evidence_id"] != three_minute["evidence_id"]


@pytest.mark.asyncio
async def test_provider_bar_closure_projects_the_same_durable_trade_bucket():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[RealtimeEvent.__table__])
    store = RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    inputs = (trade(1, second=1), trade(2, second=30, quantity=200))
    for item in inputs:
        assert await store.append(item)
    derived = aggregate_trades(inputs)[0]
    trigger = ClosedBar.model_validate(
        {
            **derived.model_dump(),
            "metadata": {
                **derived.metadata.model_dump(),
                "source": MarketDataSource.DNSE,
                "schema_version": 1,
                "raw_payload_hash": "f" * 64,
            },
            "method_version": None,
            "input_evidence_ids": (),
        }
    )

    first_redis = FakeRedis()
    projected = await TradeBarProjector(
        store, HotProjectionStore(first_redis)
    ).project(trigger)
    replay_redis = FakeRedis()
    replayed = await TradeBarProjector(
        store, HotProjectionStore(replay_redis)
    ).project(trigger)

    assert projected == (derived,)
    assert replayed == projected
    assert first_redis.values == replay_redis.values
    held = await store.query(
        EventFamily.CLOSED_BAR,
        "FPT",
        start=derived.window_start,
        end=derived.window_end + timedelta(microseconds=1),
        source=MarketDataSource.INTERNAL,
    )
    assert held.events == (derived,)
    engine.dispose()


@pytest.mark.asyncio
async def test_provider_daily_close_rolls_stored_minutes_without_merging_boards():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[RealtimeEvent.__table__])
    store = RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    minute_bars = aggregate_trades(
        (trade(1, minute=0), trade(2, minute=1, quantity=200))
    )
    for bar in minute_bars:
        assert await store.append(bar)
    expected = aggregate_bars_to_daily(minute_bars)[0]
    trigger = ClosedBar.model_validate(
        {
            **expected.model_dump(),
            "metadata": {
                **expected.metadata.model_dump(),
                "source": MarketDataSource.DNSE,
                "schema_version": 1,
                "raw_payload_hash": "e" * 64,
            },
            "method_version": None,
            "input_evidence_ids": (),
        }
    )
    redis = FakeRedis()

    projected = await TradeBarProjector(
        store, HotProjectionStore(redis)
    ).project(trigger)

    assert len(projected) == 1
    assert projected[0].resolution is BarResolution.DAY_1
    assert projected[0].volume == 300
    assert projected[0].input_evidence_ids == tuple(
        bar.metadata.evidence_id for bar in minute_bars
    )
    engine.dispose()
