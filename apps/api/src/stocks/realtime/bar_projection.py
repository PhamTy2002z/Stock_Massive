"""Durable trade-to-bar projection triggered by provider bar closure."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .aggregation import (
    ACCEPTED_TRADE_BAR_RESOLUTIONS,
    aggregate_bars_to_daily,
    aggregate_trades,
    bar_window_start,
)
from .contracts import (
    BarResolution,
    ClosedBar,
    EventFamily,
    MarketDataSource,
    NormalizedMarketEvent,
    TradeTick,
)
from .projections import HotProjectionStore
from .storage import RealtimeEventStore


class TradeBarProjector:
    """Create internal bars only after DNSE declares a bar window closed."""

    def __init__(
        self,
        store: RealtimeEventStore,
        projections: HotProjectionStore,
    ) -> None:
        self._store = store
        self._projections = projections

    async def project(self, event: NormalizedMarketEvent) -> tuple[ClosedBar, ...]:
        if not isinstance(event, ClosedBar):
            return ()
        if event.metadata.source is not MarketDataSource.DNSE:
            return ()
        if event.resolution is BarResolution.DAY_1:
            return await self._project_daily(event)

        derived: list[ClosedBar] = []
        for resolution in ACCEPTED_TRADE_BAR_RESOLUTIONS:
            start = bar_window_start(
                event.window_end - timedelta(microseconds=1), resolution
            )
            end = start + _duration(resolution)
            if end != event.window_end:
                continue
            trades = await self._trades(event, start=start, end=end)
            candidates = aggregate_trades(trades, resolutions=(resolution,))
            bar = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.window_start == start
                    and candidate.window_end == end
                    and candidate.metadata.board == event.metadata.board
                    and candidate.metadata.session is event.metadata.session
                    and candidate.metadata.units == event.metadata.units
                    and candidate.metadata.normalization_version
                    == event.metadata.normalization_version
                ),
                None,
            )
            if bar is None:
                continue
            if event.metadata.observed_time > bar.metadata.observed_time:
                bar = ClosedBar.model_validate(
                    {
                        **bar.model_dump(),
                        "metadata": {
                            **bar.metadata.model_dump(),
                            "observed_time": event.metadata.observed_time,
                        },
                    }
                )
            await self._store.append(bar)
            await self._projections.apply(bar)
            derived.append(bar)
        return tuple(derived)

    async def _project_daily(self, trigger: ClosedBar) -> tuple[ClosedBar, ...]:
        start = datetime.combine(
            trigger.metadata.trading_day,
            time.min,
            ZoneInfo("Asia/Ho_Chi_Minh"),
        )
        page_cursor = None
        minutes: list[ClosedBar] = []
        while True:
            page = await self._store.query(
                EventFamily.CLOSED_BAR,
                trigger.metadata.symbol,
                start=start,
                end=start + timedelta(days=1),
                source=MarketDataSource.INTERNAL,
                after=page_cursor,
                limit=1_000,
            )
            minutes.extend(
                item
                for item in page.events
                if isinstance(item, ClosedBar)
                and item.resolution is BarResolution.MINUTE_1
                and item.metadata.board == trigger.metadata.board
                and item.metadata.exchange is trigger.metadata.exchange
                and item.metadata.product_group is trigger.metadata.product_group
                and item.metadata.units == trigger.metadata.units
                and item.metadata.normalization_version
                == trigger.metadata.normalization_version
            )
            if page.next_cursor is None:
                break
            page_cursor = page.next_cursor
        if not minutes:
            return ()
        daily = aggregate_bars_to_daily(minutes)[0]
        if trigger.metadata.observed_time > daily.metadata.observed_time:
            daily = ClosedBar.model_validate(
                {
                    **daily.model_dump(),
                    "metadata": {
                        **daily.metadata.model_dump(),
                        "observed_time": trigger.metadata.observed_time,
                    },
                }
            )
        await self._store.append(daily)
        await self._projections.apply(daily)
        return (daily,)

    async def _trades(
        self,
        trigger: ClosedBar,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[TradeTick, ...]:
        found: list[TradeTick] = []
        cursor = None
        while True:
            page = await self._store.query(
                EventFamily.TRADE,
                trigger.metadata.symbol,
                start=start,
                end=end,
                source=MarketDataSource.DNSE,
                after=cursor,
                limit=1_000,
            )
            found.extend(
                item
                for item in page.events
                if isinstance(item, TradeTick)
                and item.metadata.board == trigger.metadata.board
                and item.metadata.session is trigger.metadata.session
                and item.metadata.exchange is trigger.metadata.exchange
                and item.metadata.product_group is trigger.metadata.product_group
                and item.metadata.units == trigger.metadata.units
                and item.metadata.normalization_version
                == trigger.metadata.normalization_version
            )
            if page.next_cursor is None:
                return tuple(found)
            cursor = page.next_cursor


def _duration(resolution: BarResolution) -> timedelta:
    return {
        BarResolution.MINUTE_1: timedelta(minutes=1),
        BarResolution.MINUTE_3: timedelta(minutes=3),
        BarResolution.MINUTE_5: timedelta(minutes=5),
        BarResolution.MINUTE_15: timedelta(minutes=15),
        BarResolution.MINUTE_30: timedelta(minutes=30),
        BarResolution.HOUR_1: timedelta(hours=1),
    }[resolution]
