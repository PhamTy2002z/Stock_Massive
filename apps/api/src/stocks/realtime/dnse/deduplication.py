"""Collision-safe duplicate classification for DNSE snapshots and pages."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

from .. import DataOutcome, DataOutcomeKind, MarketDataSource, NormalizedMarketEvent
from .metrics import AdapterMetrics


class SnapshotDeduplicator:
    def __init__(self, *, capacity: int = 100_000, metrics: AdapterMetrics | None = None) -> None:
        if capacity < 1:
            raise ValueError("deduplication capacity must be positive")
        self._capacity = capacity
        self._seen: OrderedDict[tuple[tuple[str, ...], str], str] = OrderedDict()
        self.metrics = metrics or AdapterMetrics()

    def classify(self, event: NormalizedMarketEvent) -> DataOutcome | None:
        metadata = event.metadata
        key = (metadata.observation_key, metadata.raw_payload_hash)
        previous = self._seen.get(key)
        if previous is not None:
            self._seen.move_to_end(key)
            self.metrics.increment("duplicates")
            return DataOutcome(
                kind=DataOutcomeKind.DUPLICATE,
                source=MarketDataSource.DNSE,
                request_id="dnse-dedup",
                evidence_ids=(previous,),
            )
        self._seen[key] = metadata.evidence_id
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
        return None


class EventOrderTracker:
    """Expose an out-of-order provider event as a reconciliation gap."""

    def __init__(self, *, metrics: AdapterMetrics | None = None) -> None:
        self._latest: dict[tuple[str, str, str], datetime] = {}
        self.metrics = metrics or AdapterMetrics()

    def classify(self, event: NormalizedMarketEvent) -> DataOutcome | None:
        metadata = event.metadata
        key = (metadata.event_family.value, metadata.symbol, metadata.board)
        previous = self._latest.get(key)
        if previous is not None and metadata.provider_time < previous:
            self.metrics.increment("gaps")
            return DataOutcome(
                kind=DataOutcomeKind.GAP,
                source=MarketDataSource.DNSE,
                request_id="dnse-order",
                evidence_ids=(metadata.evidence_id,),
            )
        if previous is None or metadata.provider_time > previous:
            self._latest[key] = metadata.provider_time
        return None
