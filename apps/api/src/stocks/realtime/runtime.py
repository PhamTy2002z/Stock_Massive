"""Opt-in application lifecycle owner for DNSE realtime ingestion."""

from __future__ import annotations

import asyncio
import logging

from src.core.config import Settings

from .coordinator import DnseIngestionCoordinator
from .dnse import (
    DnseCredentials,
    DnseEventParser,
    DnseRestClient,
    DnseWebSocketClient,
    ReconnectReconciler,
    RestSigner,
    SnapshotDeduplicator,
    Subscription,
    WebSocketSigner,
)
from .projections import HotProjectionStore
from .bar_projection import TradeBarProjector
from .metric_projection import CompositeProjector, MetricProjector
from .reconciliation_projection import ReconciliationProjector
from .spine import IngestionSpine
from .storage import RealtimeEventStore


logger = logging.getLogger(__name__)


class RealtimeRuntime:
    """Own the feed task and close every resource before database shutdown."""

    def __init__(
        self,
        coordinator: DnseIngestionCoordinator,
        spine: IngestionSpine,
        rest: DnseRestClient,
        *,
        symbols: tuple[str, ...],
        boards: tuple[str, ...],
        shutdown_timeout: float,
    ) -> None:
        self._coordinator = coordinator
        self._spine = spine
        self._rest = rest
        self._symbols = symbols
        self._boards = boards
        self._shutdown_timeout = shutdown_timeout
        self._feed_task: asyncio.Task[None] | None = None
        self._started = False

    async def start(self) -> None:
        await self._spine.start()
        self._started = True
        outcomes = await self._coordinator.refresh_instrument_catalog()
        if outcomes:
            logger.warning(
                "DNSE catalog refresh refused %d instrument response(s)", len(outcomes)
            )
        subscriptions = self._subscriptions()
        self._feed_task = asyncio.create_task(
            self._coordinator.run_live(subscriptions), name="dnse-realtime-feed"
        )
        self._feed_task.add_done_callback(self._report_feed_exit)

    async def stop(self) -> None:
        if self._feed_task is not None:
            self._feed_task.cancel()
            await asyncio.gather(self._feed_task, return_exceptions=True)
            self._feed_task = None
        try:
            if self._started:
                await self._spine.stop(timeout=self._shutdown_timeout)
                self._started = False
        finally:
            await self._rest.close()

    def _subscriptions(self) -> tuple[Subscription, ...]:
        subscriptions: list[Subscription] = []
        if self._symbols:
            for board in self._boards:
                for prefix in (
                    "tick_extra",
                    "foreign",
                    "expected_price",
                ):
                    subscriptions.append(
                        Subscription(f"{prefix}.{board}.json", self._symbols)
                    )
            subscriptions.append(Subscription("ohlc_closed.1.json", self._symbols))
        subscriptions.append(Subscription("market_index.VNINDEX.json"))
        subscriptions.extend(
            Subscription(f"session.STOCK.{board}.json") for board in self._boards
        )
        return tuple(subscriptions)

    @staticmethod
    def _report_feed_exit(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.exception("DNSE realtime feed stopped unexpectedly")


def build_realtime_runtime(
    settings: Settings, symbols: tuple[str, ...]
) -> RealtimeRuntime:
    if not settings.realtime_ingestion_enabled:
        raise ValueError("realtime runtime cannot be built while disabled")
    if settings.dnse_api_key is None or settings.dnse_api_secret is None:
        raise ValueError("DNSE credentials are required")
    credentials = DnseCredentials(
        settings.dnse_api_key.get_secret_value(),
        settings.dnse_api_secret.get_secret_value(),
    )
    parser = DnseEventParser()
    rest = DnseRestClient(RestSigner(credentials))
    websocket = DnseWebSocketClient(WebSocketSigner(credentials))
    store = RealtimeEventStore()
    projections = HotProjectionStore()
    spine = IngestionSpine(
        store,
        projections,
        queue_size=settings.realtime_queue_size,
        worker_count=settings.realtime_worker_count,
        derived_projector=CompositeProjector(
            TradeBarProjector(store, projections),
            ReconciliationProjector(store),
            MetricProjector(store, projections),
        ),
    )
    reconciler = ReconnectReconciler(
        rest,
        parser,
        SnapshotDeduplicator(),
    )
    coordinator = DnseIngestionCoordinator(
        spine,
        parser,
        websocket,
        rest,
        reconciler,
    )
    return RealtimeRuntime(
        coordinator,
        spine,
        rest,
        symbols=symbols,
        boards=settings.realtime_boards,
        shutdown_timeout=settings.realtime_shutdown_timeout_seconds,
    )
