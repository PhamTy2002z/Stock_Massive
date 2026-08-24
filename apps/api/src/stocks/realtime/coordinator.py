"""DNSE REST/WebSocket orchestration into the single ingestion spine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .contracts import MarketDataSource, NormalizedMarketEvent
from .dnse import (
    DnseEventParser,
    DnseRestClient,
    DnseWebSocketClient,
    ReconnectReconciler,
    Subscription,
)
from .health import FeedHealthState
from .policy import DataOutcome, DataOutcomeKind
from .spine import IngestionSpine


class DnseIngestionCoordinator:
    """Routes every admitted DNSE delivery through one persistence path."""

    def __init__(
        self,
        spine: IngestionSpine,
        parser: DnseEventParser,
        websocket: DnseWebSocketClient,
        rest: DnseRestClient,
        reconciler: ReconnectReconciler,
        trading_day_clock: Callable[[], date] | None = None,
    ) -> None:
        self._spine = spine
        self._parser = parser
        self._websocket = websocket
        self._rest = rest
        self._reconciler = reconciler
        self._trading_day_clock = trading_day_clock or (
            lambda: datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        )
        websocket.set_reconnect_handler(self._after_websocket_reconnect)

    async def bootstrap_instruments(
        self, symbols: tuple[str, ...], *, board: str | None = None
    ) -> tuple[DataOutcome, ...]:
        outcomes: list[DataOutcome] = []
        for symbol in symbols:
            result = await self._rest.security_definition(symbol, board)
            if result.outcome is not None:
                outcomes.append(result.outcome)
                continue
            payload = result.data
            if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                payload = payload["data"]
            if not isinstance(payload, dict):
                outcomes.append(_invalid_outcome(result.request_id))
                continue
            wire = dict(payload)
            wire.setdefault("T", "sd")
            wire.setdefault("symbol", symbol)
            parsed = self._parser.parse(wire, request_id=result.request_id)
            if parsed.outcome is not None:
                outcomes.append(parsed.outcome)
            else:
                await self._spine.submit(_required_event(parsed.event))
        return tuple(outcomes)

    async def reconcile(
        self,
        *,
        symbol: str,
        family: str,
        trading_day: date,
        board: str | None = None,
    ) -> tuple[DataOutcome, ...]:
        await self._spine.set_feed_health(
            FeedHealthState.RECONNECTING, reason="rest_reconciliation"
        )
        batch = await self._reconciler.reconcile(
            symbol=symbol,
            family=family,
            trading_day=trading_day,
            board=board,
        )
        for event in batch.recovered:
            await self._spine.submit(event)
        await self._spine.set_feed_health(FeedHealthState.CONNECTED)
        return batch.outcomes

    async def eod_check(
        self, symbols: tuple[str, ...], *, board: str | None = None
    ) -> tuple[DataOutcome, ...]:
        """Run bounded close checks without turning responses into fake events."""
        outcomes: list[DataOutcome] = []
        for symbol in symbols:
            result = await self._rest.close_price(symbol, board)
            if result.outcome is not None:
                outcomes.append(result.outcome)
        return tuple(outcomes)

    async def run_live(self, subscriptions: tuple[Subscription, ...]) -> None:
        await self._spine.set_feed_health(FeedHealthState.STARTING)
        try:
            await self._websocket.connect()
            for subscription in subscriptions:
                await self._websocket.subscribe(subscription)
            await self._spine.set_feed_health(FeedHealthState.CONNECTED)
            sequence = 0
            async for payload in self._websocket.stream():
                sequence += 1
                parsed = self._parser.parse(
                    payload, request_id=f"dnse-ws-{sequence}"
                )
                if parsed.outcome is not None:
                    await self._spine.set_feed_health(
                        FeedHealthState.DEGRADED, reason="parse_refusal"
                    )
                    continue
                await self._spine.submit(_required_event(parsed.event))
        except Exception:
            await self._spine.set_feed_health(
                FeedHealthState.DISCONNECTED, reason="websocket_failure"
            )
            raise
        finally:
            await self._websocket.close()

    async def _after_websocket_reconnect(
        self, subscriptions: tuple[Subscription, ...]
    ) -> None:
        family_by_prefix = {
            "tick": "trades",
            "tick_extra": "trades",
            "top_price": "quotes",
            "foreign": "foreign-trading",
            "expected_price": "expected-price",
        }
        await self._spine.set_feed_health(
            FeedHealthState.RECONNECTING, reason="rest_reconciliation"
        )
        unsupported = False
        for subscription in subscriptions:
            family = family_by_prefix.get(subscription.channel.split(".", 1)[0])
            if family is None:
                unsupported = True
                continue
            for symbol in subscription.symbols:
                batch = await self._reconciler.reconcile(
                    symbol=symbol,
                    family=family,
                    trading_day=self._trading_day_clock(),
                )
                for event in batch.recovered:
                    await self._spine.submit(event)
        if unsupported:
            await self._spine.set_feed_health(
                FeedHealthState.DEGRADED,
                reason="reconciliation_unavailable",
            )
        else:
            await self._spine.set_feed_health(FeedHealthState.CONNECTED)


def _required_event(event: NormalizedMarketEvent | None) -> NormalizedMarketEvent:
    if event is None:
        raise RuntimeError("DNSE parser returned neither event nor outcome")
    return event


def _invalid_outcome(request_id: str) -> DataOutcome:
    return DataOutcome(
        kind=DataOutcomeKind.INVALID_REQUEST,
        source=MarketDataSource.DNSE,
        request_id=request_id,
    )
