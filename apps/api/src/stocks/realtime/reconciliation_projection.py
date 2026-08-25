"""Shadow reconciliation triggered after durable bar projection."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .contracts import (
    BarResolution,
    ClosedBar,
    EventFamily,
    MarketDataSource,
    NormalizedMarketEvent,
)
from .policy import (
    STRICT_RECONCILIATION_PROFILE_V1,
    ComparisonScope,
    ReconciliationToleranceProfile,
)
from .reconciliation import build_reconciliation_audit, reconcile_bars
from .storage import RealtimeEventStore


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class ReconciliationProjector:
    """Record disagreements without blocking or mutating accepted evidence."""

    def __init__(
        self,
        store: RealtimeEventStore,
        profile: ReconciliationToleranceProfile = STRICT_RECONCILIATION_PROFILE_V1,
    ) -> None:
        self._store = store
        self._profile = profile

    async def project(
        self, event: NormalizedMarketEvent
    ) -> tuple[NormalizedMarketEvent, ...]:
        if not isinstance(event, ClosedBar):
            return ()

        counterpart_source, scope = self._comparison_target(event)
        if counterpart_source is None or scope is None:
            return ()
        counterpart = await self._counterpart(event, counterpart_source)
        if counterpart is None:
            return ()

        result = reconcile_bars(counterpart, event, self._profile, scope=scope)
        await self._store.append_reconciliation(
            build_reconciliation_audit(result, self._profile)
        )
        return ()

    @staticmethod
    def _comparison_target(
        event: ClosedBar,
    ) -> tuple[MarketDataSource | None, ComparisonScope | None]:
        if event.metadata.source is MarketDataSource.DNSE:
            return (
                MarketDataSource.INTERNAL,
                ComparisonScope.DAILY
                if event.resolution is BarResolution.DAY_1
                else ComparisonScope.INTRADAY,
            )
        if (
            event.metadata.source is MarketDataSource.FIINQUANT
            and event.resolution is BarResolution.DAY_1
        ):
            return MarketDataSource.DNSE, ComparisonScope.CROSS_PROVIDER
        return None, None

    async def _counterpart(
        self,
        trigger: ClosedBar,
        source: MarketDataSource,
    ) -> ClosedBar | None:
        start = datetime.combine(trigger.metadata.trading_day, time.min, VN_TZ)
        end = start + timedelta(days=1)
        cursor = None
        candidates: list[ClosedBar] = []
        while True:
            page = await self._store.query(
                EventFamily.CLOSED_BAR,
                trigger.metadata.symbol,
                start=start,
                end=end,
                source=source,
                after=cursor,
                limit=1_000,
            )
            candidates.extend(
                item
                for item in page.events
                if isinstance(item, ClosedBar)
                and item.resolution is trigger.resolution
                and item.metadata.board == trigger.metadata.board
                and (
                    item.resolution is BarResolution.DAY_1
                    or (
                        item.window_start == trigger.window_start
                        and item.window_end == trigger.window_end
                    )
                )
            )
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                item.metadata.observed_time,
                item.metadata.evidence_id,
            ),
        )
