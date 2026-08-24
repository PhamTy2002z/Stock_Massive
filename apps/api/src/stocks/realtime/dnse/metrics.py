"""Low-cardinality operational metrics for the DNSE adapter."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    counters: Mapping[str, int]
    gauges: Mapping[str, int]
    latency_ms_total: float
    latency_samples: int


class AdapterMetrics:
    _ALLOWED = frozenset(
        {
            "requests",
            "quota_refusals",
            "disconnects",
            "parse_failures",
            "duplicates",
            "gaps",
            "queue_pressure",
            "reconnects",
        }
    )

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters = {name: 0 for name in self._ALLOWED}
        self._gauges = {"queue_depth": 0, "quota_remaining": 0}
        self._latency_ms_total = 0.0
        self._latency_samples = 0

    def increment(self, name: str, value: int = 1) -> None:
        if name not in self._ALLOWED or value < 0:
            raise ValueError("unsupported metric or negative increment")
        with self._lock:
            self._counters[name] += value

    def gauge(self, name: str, value: int) -> None:
        if name not in self._gauges or value < 0:
            raise ValueError("unsupported metric or negative gauge")
        with self._lock:
            self._gauges[name] = value

    def observe_latency(self, milliseconds: float) -> None:
        if milliseconds < 0:
            raise ValueError("latency cannot be negative")
        with self._lock:
            self._latency_ms_total += milliseconds
            self._latency_samples += 1

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                counters=MappingProxyType(dict(self._counters)),
                gauges=MappingProxyType(dict(self._gauges)),
                latency_ms_total=self._latency_ms_total,
                latency_samples=self._latency_samples,
            )
