"""Bounded at-least-once ingestion worker with durable overflow and replay."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Protocol

from .contracts import EventFamily, NormalizedMarketEvent
from .health import DataHealthState, FeedHealthState, HealthSnapshot, HealthTracker
from .projections import HotProjectionStore, ProjectionUnavailable
from .storage import RealtimeEventStore


class DerivedProjector(Protocol):
    async def project(
        self, event: NormalizedMarketEvent
    ) -> tuple[NormalizedMarketEvent, ...]: ...


class IngestionSpine:
    """One normalized path from adapter events to storage and hot state."""

    def __init__(
        self,
        store: RealtimeEventStore,
        projections: HotProjectionStore,
        *,
        consumer: str = "dnse-realtime",
        queue_size: int = 2_000,
        worker_count: int = 1,
        health: HealthTracker | None = None,
        derived_projector: DerivedProjector | None = None,
    ) -> None:
        if queue_size < 1 or not 1 <= worker_count <= 8:
            raise ValueError("invalid realtime queue or worker count")
        self._store = store
        self._projections = projections
        self._consumer = consumer
        self._queue: asyncio.Queue[NormalizedMarketEvent] = asyncio.Queue(queue_size)
        self._worker_count = worker_count
        self._workers: list[asyncio.Task[None]] = []
        self._accepting = False
        self._health = health or HealthTracker()
        self._derived_projector = derived_projector
        self._health_lock = asyncio.Lock()
        self._published_health: dict[str, tuple[str, str | None]] = {}

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    async def start(self) -> None:
        if self._workers:
            return
        self._accepting = True
        await self._publish_health(self._health.feed(FeedHealthState.STARTING))
        await self.recover_spills()
        self._workers = [
            asyncio.create_task(self._worker(), name=f"realtime-ingestion-{index}")
            for index in range(self._worker_count)
        ]
        await self._publish_health(self._health.feed(FeedHealthState.CONNECTED))

    async def submit(self, event: NormalizedMarketEvent) -> bool:
        if not self._accepting:
            raise RuntimeError("realtime ingestion is not accepting events")
        if self._queue.full():
            spilled = await self._store.spill(event, "queue_full")
            if spilled:
                self._health.spilled()
            await self._publish_health(
                self._health.feed(FeedHealthState.DEGRADED, reason="queue_pressure")
            )
            await self._publish_health(
                self._health.data(DataHealthState.DEGRADED, reason="durable_spill")
            )
            return False
        self._queue.put_nowait(event)
        self._health.queue(self._queue.qsize())
        return True

    async def set_feed_health(
        self, status: FeedHealthState, *, reason: str | None = None
    ) -> None:
        await self._publish_health(self._health.feed(status, reason=reason))

    async def recover_spills(self, *, limit: int = 1_000) -> int:
        recovered = 0
        for spill in await self._store.pending_spills(limit):
            await self._process(spill.event)
            await self._store.mark_spill_recovered(spill.spill_id)
            recovered += 1
        return recovered

    async def replay_partition(
        self,
        trading_day: date,
        family: EventFamily,
        *,
        rebuild_projection: bool = False,
    ) -> tuple[NormalizedMarketEvent, ...]:
        checkpoint = None
        if not rebuild_projection:
            key = f"{trading_day.isoformat()}:{family.value}"
            checkpoint = await self._store.load_checkpoint(self._consumer, key)
        events = await self._store.replay(trading_day, family, after=checkpoint)
        for event in events:
            await self._apply_projection(event)
            if self._derived_projector is not None:
                await self._derived_projector.project(event)
            await self._store.save_checkpoint(self._consumer, event)
        return events

    async def stop(self, *, timeout: float = 10.0) -> None:
        if timeout <= 0:
            raise ValueError("shutdown timeout must be positive")
        self._accepting = False
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except TimeoutError:
            await self._spill_queued("shutdown_timeout")
            await self._publish_health(
                self._health.feed(FeedHealthState.DEGRADED, reason="shutdown_timeout")
            )
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        await self._publish_health(self._health.feed(FeedHealthState.STOPPED))

    async def _worker(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                await self._process(event)
            except asyncio.CancelledError:
                await self._store.spill(event, "worker_cancelled")
                raise
            except Exception:
                await self._store.spill(event, "processing_failure")
                await self._publish_health(
                    self._health.feed(
                        FeedHealthState.DEGRADED, reason="processing_failure"
                    )
                )
            finally:
                self._queue.task_done()
                self._health.queue(self._queue.qsize())

    async def _process(self, event: NormalizedMarketEvent) -> None:
        inserted = await self._store.append(event)
        await self._apply_projection(event)
        if inserted and self._derived_projector is not None:
            await self._derived_projector.project(event)
        await self._store.save_checkpoint(self._consumer, event)
        self._health.processed(duplicate=not inserted)
        await self._publish_health(self._health.data(DataHealthState.HEALTHY))

    async def _apply_projection(self, event: NormalizedMarketEvent) -> None:
        try:
            await self._projections.apply(event)
        except ProjectionUnavailable:
            await self._publish_health(
                self._health.data(DataHealthState.DEGRADED, reason="redis_unavailable"),
                redis=False,
            )
            raise

    async def _publish_health(
        self, snapshot: HealthSnapshot, *, redis: bool = True
    ) -> None:
        async with self._health_lock:
            state = (snapshot.status, snapshot.reason)
            if self._published_health.get(snapshot.scope) == state:
                return
            await self._store.save_health(snapshot)
            self._published_health[snapshot.scope] = state
            if redis:
                try:
                    await self._projections.save_health(snapshot)
                except ProjectionUnavailable:
                    if snapshot.status != DataHealthState.DEGRADED.value:
                        degraded = self._health.data(
                            DataHealthState.DEGRADED, reason="redis_unavailable"
                        )
                        await self._store.save_health(degraded)

    async def _spill_queued(self, reason: str) -> None:
        while not self._queue.empty():
            event = self._queue.get_nowait()
            try:
                if await self._store.spill(event, reason):
                    self._health.spilled()
            finally:
                self._queue.task_done()
