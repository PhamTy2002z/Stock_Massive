"""Realtime Market Monitor overlay keeps board, unit, and health boundaries."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from src.stocks.monitor.analytics import StockReading
from src.stocks.monitor.realtime import (
    build_realtime_overlay,
    load_realtime_overlay,
    rank_market_flows,
)
from src.stocks.monitor.schemas import MonitorState
from src.stocks.providers.contracts import Exchange
from src.stocks.realtime.health import HealthSnapshot
from src.stocks.realtime.metrics import (
    ForeignFlowProjection,
    TradeMetricsProjection,
)
from src.stocks.realtime.projections import HotProjectionStore, ProjectionUnavailable
from src.stocks.realtime.service import (
    RealtimeProjectionBatchResponse,
    RealtimeProjectionResponse,
)
from src.stocks.realtime.contracts import QualityState


NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
EVIDENCE = "evt_" + "1" * 64


class BulkRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.mget_calls = 0

    def get(self, key: str):
        return self.values.get(key)

    def mget(self, *keys: str):
        self.mget_calls += 1
        return [self.values.get(key) for key in keys]

    def set(self, key: str, value: str, **_kwargs):
        self.values[key] = value
        return True

    def eval(self, _script, *positional, **keyword):
        keys = keyword["keys"] if keyword else positional[1 : 1 + positional[0]]
        args = keyword["args"] if keyword else positional[1 + positional[0] :]
        self.values[keys[0]] = args[0]
        self.values[keys[1]] = args[1]
        return 1


def trade_metric(symbol: str, *, board: str = "G1") -> TradeMetricsProjection:
    return TradeMetricsProjection(
        symbol=symbol,
        board=board,
        trading_day=date(2026, 8, 24),
        as_of=NOW,
        evidence_ids=(EVIDENCE,),
        method_version=1,
        quality_state=QualityState.VALID,
        units={
            "session_vwap_vnd": "VND",
            "session_volume_shares": "share",
            "signed_volume_shares": "share",
            "unknown_side_volume_shares": "share",
            "trade_intensity_per_minute": "trade/minute",
            "volume_acceleration": "ratio",
        },
        session_vwap_vnd=Decimal("110"),
        session_volume_shares=1_000,
        signed_volume_shares=100,
        unknown_side_volume_shares=0,
        trade_intensity_per_minute=Decimal("2"),
        volume_acceleration=Decimal("0.25"),
    )


def foreign_metric(symbol: str) -> ForeignFlowProjection:
    return ForeignFlowProjection(
        symbol=symbol,
        board="G1",
        trading_day=date(2026, 8, 24),
        as_of=NOW,
        evidence_ids=(EVIDENCE,),
        method_version=1,
        quality_state=QualityState.VALID,
        units={
            "buy_volume_shares": "share",
            "sell_volume_shares": "share",
            "net_volume_shares": "share",
            "buy_value_vnd": "VND",
            "sell_value_vnd": "VND",
            "net_value_vnd": "VND",
            "current_room_shares": "share",
            "total_room_shares": "share",
        },
        buy_volume_shares=200,
        sell_volume_shares=50,
        net_volume_shares=150,
        buy_value_vnd=Decimal("22000"),
        sell_value_vnd=Decimal("5500"),
        net_value_vnd=Decimal("16500"),
        current_room_shares=1_000,
        total_room_shares=2_000,
    )


def eod_stock(symbol: str) -> StockReading:
    return StockReading(
        symbol=symbol,
        name=symbol,
        exchange=Exchange.HOSE,
        sector_code="10",
        sector_name="Ngân hàng",
        last_price_vnd=100.0,
        return_1d_pct=1.0,
        return_5d_pct=2.0,
        return_20d_pct=3.0,
        above_ma20=True,
        above_ma50=True,
        above_ma200=False,
        liquidity_ratio=1.2,
        adtv20_vnd=100_000.0,
        foreign_net_1d_vnd=10.0,
        foreign_net_5d_vnd=50.0,
        foreign_net_20d_vnd=200.0,
        foreign_flow_over_adtv=0.002,
        issues=(),
    )


@pytest.mark.asyncio
async def test_projection_bulk_read_is_one_call_stable_and_g1_only() -> None:
    redis = BulkRedis()
    store = HotProjectionStore(redis)
    await store.save_metric(trade_metric("BBB"))
    await store.save_metric(trade_metric("AAA"))
    await store.save_metric(trade_metric("AAA", board="G4"))
    redis.mget_calls = 0

    result = await store.read_metrics(
        ("BBB", "AAA"),
        "G1",
        kinds=("trade_metrics", "foreign_flow"),
    )

    assert redis.mget_calls == 1
    assert tuple(result) == (("AAA", "G1"), ("BBB", "G1"))
    assert tuple(result[("AAA", "G1")]) == ("trade_metrics",)


def test_partial_overlay_never_claims_complete_market_realtime() -> None:
    batch = RealtimeProjectionBatchResponse(
        board="G1",
        items=(
            RealtimeProjectionResponse(
                symbol="AAA",
                board="G1",
                projections={
                    "trade_metrics": trade_metric("AAA").model_dump(mode="json"),
                    "foreign_flow": foreign_metric("AAA").model_dump(mode="json"),
                },
            ),
        ),
        feed=HealthSnapshot(
            scope="feed",
            status="connected",
            observed_at=NOW,
        ),
        data=HealthSnapshot(
            scope="data",
            status="healthy",
            observed_at=NOW,
        ),
    )

    overlay = build_realtime_overlay(
        batch,
        eligible_symbols=("AAA", "BBB"),
        eod_stocks=(eod_stock("AAA"), eod_stock("BBB")),
        now=NOW,
    )

    assert overlay.state is MonitorState.PARTIAL
    assert (overlay.eligible, overlay.evaluated) == (2, 1)
    assert overlay.items[0].active_net_value_vnd == Decimal("11000")
    assert overlay.items[0].active_flow_over_adtv == Decimal("0.11")
    assert overlay.items[0].quadrant == "price_up_flow_in"


@pytest.mark.asyncio
async def test_disconnected_overlay_leaves_eod_available() -> None:
    class DisconnectedService:
        async def metrics_many(self, *_args, **_kwargs):
            raise ProjectionUnavailable("redis unavailable")

    overlay = await load_realtime_overlay(
        DisconnectedService(),
        eligible_symbols=("AAA",),
        eod_stocks=(eod_stock("AAA"),),
        now=NOW,
    )

    assert overlay.state is MonitorState.DISCONNECTED
    assert overlay.evaluated == 0
    assert overlay.eod_available is True
    assert overlay.issues == ("realtime_projection_unavailable",)


@pytest.mark.asyncio
async def test_market_overlay_chunks_cohorts_larger_than_bulk_read_bound() -> None:
    class ChunkedService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        async def metrics_many(self, symbols, board="G1"):
            self.calls.append(symbols)
            return RealtimeProjectionBatchResponse(
                board=board,
                items=tuple(
                    RealtimeProjectionResponse(symbol=symbol, board=board, projections={})
                    for symbol in symbols
                ),
                feed=None,
                data=None,
            )

    service = ChunkedService()
    symbols = tuple(f"S{index:03d}" for index in range(205))

    overlay = await load_realtime_overlay(
        service,
        eligible_symbols=symbols,
        eod_stocks=(),
        now=NOW,
    )

    assert [len(call) for call in service.calls] == [100, 100, 5]
    assert overlay.eligible == 205
    assert overlay.evaluated == 0


def test_stale_projection_is_reported_without_zeroing_metrics() -> None:
    old = NOW - timedelta(minutes=10)
    payload = trade_metric("AAA").model_copy(update={"as_of": old})
    batch = RealtimeProjectionBatchResponse(
        board="G1",
        items=(
            RealtimeProjectionResponse(
                symbol="AAA",
                board="G1",
                projections={"trade_metrics": payload.model_dump(mode="json")},
            ),
        ),
        feed=None,
        data=None,
    )

    overlay = build_realtime_overlay(
        batch,
        eligible_symbols=("AAA",),
        eod_stocks=(eod_stock("AAA"),),
        now=NOW,
        stale_after=timedelta(minutes=2),
    )

    assert overlay.state is MonitorState.STALE
    assert overlay.items[0].active_net_value_vnd == Decimal("11000")


def test_recovered_feed_and_vnd_flow_reversal_are_explicit() -> None:
    batch = RealtimeProjectionBatchResponse(
        board="G1",
        items=(
            RealtimeProjectionResponse(
                symbol="AAA",
                board="G1",
                projections={
                    "foreign_flow": foreign_metric("AAA")
                    .model_copy(update={"net_value_vnd": Decimal("-10")})
                    .model_dump(mode="json")
                },
            ),
        ),
        feed=HealthSnapshot(
            scope="feed",
            status="connected",
            reason="recovered",
            observed_at=NOW,
        ),
        data=HealthSnapshot(scope="data", status="healthy", observed_at=NOW),
    )
    overlay = build_realtime_overlay(
        batch,
        eligible_symbols=("AAA",),
        eod_stocks=(eod_stock("AAA"),),
        now=NOW,
    )

    ranks = rank_market_flows((eod_stock("AAA"),), overlay)

    assert overlay.recovered is True
    assert "realtime_feed_recovered" in overlay.issues
    assert ranks.reversals == ("AAA",)


def test_flow_ranking_uses_the_selected_horizon() -> None:
    long_in_short_out = replace(
        eod_stock("AAA"),
        foreign_net_1d_vnd=-100.0,
        foreign_net_20d_vnd=500.0,
    )
    long_out_short_in = replace(
        eod_stock("BBB"),
        foreign_net_1d_vnd=200.0,
        foreign_net_20d_vnd=-300.0,
    )
    live = build_realtime_overlay(
        RealtimeProjectionBatchResponse(
            board="G1",
            items=(
                RealtimeProjectionResponse(
                    symbol="AAA",
                    board="G1",
                    projections={
                        "foreign_flow": foreign_metric("AAA")
                        .model_copy(update={"net_value_vnd": Decimal("10")})
                        .model_dump(mode="json")
                    },
                ),
            ),
            feed=None,
            data=None,
        ),
        eligible_symbols=("AAA", "BBB"),
        eod_stocks=(long_in_short_out, long_out_short_in),
        now=NOW,
    )

    one_day = rank_market_flows(
        (long_in_short_out, long_out_short_in), live, horizon=1
    )
    twenty_day = rank_market_flows(
        (long_in_short_out, long_out_short_in), live, horizon=20
    )

    assert one_day.inflows == ("BBB",)
    assert one_day.outflows == ("AAA",)
    assert twenty_day.inflows == ("AAA",)
    assert twenty_day.outflows == ("BBB",)
    assert one_day.reversals == ("AAA",)
    assert twenty_day.reversals == ()
