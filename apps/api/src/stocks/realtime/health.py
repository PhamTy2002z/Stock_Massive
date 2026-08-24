"""Queryable health contracts for the realtime ingestion boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Callable

from pydantic import Field, model_validator

from .contracts import RealtimeContract


class FeedHealthState(str, Enum):
    STARTING = "starting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    STOPPED = "stopped"


class DataHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    GAPPED = "gapped"
    STALE = "stale"


class HealthSnapshot(RealtimeContract):
    scope: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9:_-]+$")
    status: str = Field(min_length=1, max_length=32, pattern=r"^[a-z_]+$")
    reason: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9:_-]+$")
    observed_at: datetime
    queue_depth: int = Field(default=0, ge=0)
    spill_count: int = Field(default=0, ge=0)
    processed_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_status_for_scope(self):
        allowed = {
            "feed": {state.value for state in FeedHealthState},
            "data": {state.value for state in DataHealthState},
        }
        if self.scope in allowed and self.status not in allowed[self.scope]:
            raise ValueError("health status does not match its scope")
        return self


class HealthTracker:
    """Small state owner that never turns a degradation into a silent success."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._queue_depth = 0
        self._spill_count = 0
        self._processed_count = 0
        self._duplicate_count = 0

    def feed(self, status: FeedHealthState, *, reason: str | None = None) -> HealthSnapshot:
        return self._snapshot("feed", status.value, reason)

    def data(self, status: DataHealthState, *, reason: str | None = None) -> HealthSnapshot:
        return self._snapshot("data", status.value, reason)

    def queue(self, depth: int) -> None:
        self._queue_depth = depth

    def processed(self, *, duplicate: bool = False) -> None:
        self._processed_count += 1
        if duplicate:
            self._duplicate_count += 1

    def spilled(self) -> None:
        self._spill_count += 1

    def _snapshot(self, scope: str, status: str, reason: str | None) -> HealthSnapshot:
        return HealthSnapshot(
            scope=scope,
            status=status,
            reason=reason,
            observed_at=self._clock(),
            queue_depth=self._queue_depth,
            spill_count=self._spill_count,
            processed_count=self._processed_count,
            duplicate_count=self._duplicate_count,
        )
