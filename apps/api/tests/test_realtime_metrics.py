"""Deterministic trade and foreign-flow projections retain provenance."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.stocks.models import RealtimeEvent
from src.stocks.realtime import (
    AggressorSide,
    EventFamily,
    EventMetadata,
    Exchange,
    ForeignFlowSnapshot,
    HotProjectionStore,
    MarketDataSource,
    MetricProjector,
    QualityState,
    RealtimeEventStore,
    TradeTick,
    TradingSession,
)
from src.stocks.realtime.metrics import (
    project_foreign_flow,
    project_trade_metrics,
    project_upcom_reference_input,
)

from .test_realtime_aggregation import trade
from .test_realtime_ingestion import FakeRedis


def test_trade_metrics_publish_vwap_signed_flow_intensity_and_acceleration():
    events = tuple(
        trade(
            index + 1,
            minute=index,
            quantity=100 if index < 5 else 200,
            price="71000" if index < 5 else "72000",
        ).model_copy(
            update={
                "aggressor_side": (
                    AggressorSide.BUY if index % 2 else AggressorSide.SELL
                )
            }
        )
        for index in range(11)
    )

    projection = project_trade_metrics(events)

    assert projection.session_volume_shares == 1_700
    assert projection.session_vwap_vnd == Decimal("121900000") / 1_700
    assert projection.signed_volume_shares == -100
    assert projection.trade_intensity_per_minute == Decimal("1.1")
    assert projection.volume_acceleration is not None
    assert projection.units["session_vwap_vnd"] == "VND"
    assert projection.evidence_ids == tuple(
        event.metadata.evidence_id for event in events
    )


def test_foreign_flow_uses_latest_cumulative_snapshot_and_keeps_health():
    base = trade(1).metadata

    def snapshot(sequence, buy, sell):
        stamp = base.provider_time + timedelta(seconds=sequence)
        metadata = base.model_dump()
        metadata.update(
            {
                "event_family": EventFamily.FOREIGN_FLOW,
                "provider_time": stamp,
                "observed_time": stamp,
                "raw_payload_hash": f"{sequence + 100:064x}",
                "quality_state": QualityState.VALID,
                "units": {
                    "price": "none",
                    "quantity": "share",
                    "value": "VND",
                },
            }
        )
        return ForeignFlowSnapshot(
            metadata=EventMetadata.model_validate(metadata),
            buy_volume=buy,
            sell_volume=sell,
            buy_value_vnd=Decimal(buy * 10_000),
            sell_value_vnd=Decimal(sell * 10_000),
            current_room=1_000,
            total_room=2_000,
        )

    projection = project_foreign_flow((snapshot(1, 100, 40), snapshot(2, 180, 70)))

    assert projection.net_volume_shares == 110
    assert projection.net_value_vnd == Decimal("1100000")
    assert projection.quality_state is QualityState.VALID
    assert projection.units["net_volume_shares"] == "share"


def test_upcom_reference_input_excludes_odd_lot_and_auction_activity():
    eligible = trade(1, board="G1", price="15000", quantity=100)
    eligible = TradeTick.model_validate(
        eligible.model_dump() | {
            "metadata": eligible.metadata.model_dump() | {"exchange": Exchange.UPCOM}
        }
    )
    odd_lot = trade(2, board="G4", price="20000", quantity=10)
    odd_lot = TradeTick.model_validate(
        odd_lot.model_dump() | {
            "metadata": odd_lot.metadata.model_dump()
            | {"exchange": Exchange.UPCOM, "board": "G4"}
        }
    )
    auction = trade(3, board="G1", price="30000", quantity=100)
    auction = TradeTick.model_validate(
        auction.model_dump() | {
            "metadata": auction.metadata.model_dump()
            | {"exchange": Exchange.UPCOM, "session": TradingSession.ATC}
        }
    )
    negotiated = trade(4, board="G2", price="40000", quantity=1_000)
    negotiated = TradeTick.model_validate(
        negotiated.model_dump()
        | {
            "metadata": negotiated.metadata.model_dump()
            | {"exchange": Exchange.UPCOM, "board": "G2"}
        }
    )

    projection = project_upcom_reference_input(
        (eligible, odd_lot, auction, negotiated)
    )

    assert projection.round_lot_continuous_vwap_vnd == Decimal("15000")
    assert projection.eligible_volume_shares == 100
    assert projection.evidence_ids == (eligible.metadata.evidence_id,)
    assert projection.units["round_lot_continuous_vwap_vnd"] == "VND"


def test_metric_projection_refuses_mixed_provider_evidence():
    left = trade(1)
    right = TradeTick.model_validate(
        trade(2).model_dump()
        | {
            "metadata": trade(2).metadata.model_dump()
            | {
                "source": MarketDataSource.FIINQUANT,
                "raw_payload_hash": "a" * 64,
            }
        }
    )

    with pytest.raises(ValueError, match="one market identity"):
        project_trade_metrics((left, right))


@pytest.mark.asyncio
async def test_metric_projection_replay_rebuilds_identical_hot_state():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[RealtimeEvent.__table__])
    store = RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    events = tuple(trade(index + 1, minute=index) for index in range(3))
    live_redis = FakeRedis()
    live = MetricProjector(store, HotProjectionStore(live_redis))
    for event in events:
        assert await store.append(event)
        await live.project(event)

    replay_redis = FakeRedis()
    replay = MetricProjector(store, HotProjectionStore(replay_redis))
    for event in await store.replay(events[0].metadata.trading_day, EventFamily.TRADE):
        await replay.project(event)

    assert live_redis.values == replay_redis.values
    metric = await HotProjectionStore(replay_redis).read_metric(
        "trade_metrics", "FPT", "G1"
    )
    assert metric is not None
    assert metric["session_volume_shares"] == 300
    engine.dispose()
    HotProjectionStore,
    MetricProjector,
