"""Rebuildable hot metrics derived only from durable normalized evidence."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .contracts import (
    Exchange,
    EventFamily,
    ForeignFlowSnapshot,
    MarketDataSource,
    NormalizedMarketEvent,
    TradeTick,
    TradingSession,
)
from .metrics import (
    project_foreign_flow,
    project_trade_metrics,
    project_upcom_reference_input,
)
from .projections import HotProjectionStore
from .storage import RealtimeEventStore


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class MetricProjector:
    """Refresh one source-neutral metric identity after its evidence is durable."""

    def __init__(
        self,
        store: RealtimeEventStore,
        projections: HotProjectionStore,
    ) -> None:
        self._store = store
        self._projections = projections

    async def project(
        self, event: NormalizedMarketEvent
    ) -> tuple[NormalizedMarketEvent, ...]:
        if event.metadata.source is not MarketDataSource.DNSE:
            return ()
        if isinstance(event, TradeTick):
            trades = await self._events(event, EventFamily.TRADE, TradeTick)
            same_stream = tuple(
                item
                for item in trades
                if item.metadata.board == event.metadata.board
                and item.metadata.exchange is event.metadata.exchange
                and item.metadata.product_group is event.metadata.product_group
                and item.metadata.session is event.metadata.session
            )
            await self._projections.save_metric(project_trade_metrics(same_stream))
            if event.metadata.exchange is Exchange.UPCOM and any(
                item.metadata.board == "G1"
                and item.metadata.session is TradingSession.CONTINUOUS
                for item in trades
            ):
                await self._projections.save_metric(
                    project_upcom_reference_input(trades)
                )
        elif isinstance(event, ForeignFlowSnapshot):
            snapshots = await self._events(
                event,
                EventFamily.FOREIGN_FLOW,
                ForeignFlowSnapshot,
            )
            same_stream = tuple(
                item
                for item in snapshots
                if item.metadata.board == event.metadata.board
                and item.metadata.exchange is event.metadata.exchange
                and item.metadata.product_group is event.metadata.product_group
                and item.metadata.session is event.metadata.session
            )
            await self._projections.save_metric(project_foreign_flow(same_stream))
        return ()

    async def _events(self, trigger, family, event_type):
        start = datetime.combine(trigger.metadata.trading_day, time.min, VN_TZ)
        end = start + timedelta(days=1)
        found = []
        cursor = None
        while True:
            page = await self._store.query(
                family,
                trigger.metadata.symbol,
                start=start,
                end=end,
                source=trigger.metadata.source,
                after=cursor,
                limit=1_000,
            )
            found.extend(item for item in page.events if isinstance(item, event_type))
            if page.next_cursor is None:
                return tuple(found)
            cursor = page.next_cursor


class CompositeProjector:
    """Run independent derived projectors behind one ingestion-spine seam."""

    def __init__(self, *projectors) -> None:
        self._projectors = projectors

    async def project(
        self, event: NormalizedMarketEvent
    ) -> tuple[NormalizedMarketEvent, ...]:
        derived: list[NormalizedMarketEvent] = []
        for projector in self._projectors:
            derived.extend(await projector.project(event))
        return tuple(derived)
