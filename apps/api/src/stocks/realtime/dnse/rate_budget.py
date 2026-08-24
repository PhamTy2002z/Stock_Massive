"""Conservative endpoint-family rate budgets learned from response headers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Mapping


class EndpointFamily(str, Enum):
    OHLC = "ohlc"
    EVENTS = "events"
    INSTRUMENTS = "instruments"
    REFERENCE = "reference"
    UNPUBLISHED = "unpublished"


_PUBLISHED = {
    EndpointFamily.OHLC: (50_000, 100_000),
    EndpointFamily.EVENTS: (10_000, 100_000),
    EndpointFamily.INSTRUMENTS: (10_000, 100_000),
    EndpointFamily.REFERENCE: (1_000, 10_000),
    EndpointFamily.UNPUBLISHED: (60, 500),
}


@dataclass(slots=True)
class _Window:
    hourly_remaining: int
    daily_remaining: int
    reset_at: float
    daily_reset_at: float


class RateBudget:
    def __init__(self, *, clock=time.time) -> None:
        self._clock = clock
        self._lock = Lock()
        now = clock()
        self._windows = {
            family: _Window(hourly, daily, now + 3600, now + 86400)
            for family, (hourly, daily) in _PUBLISHED.items()
        }

    def acquire(self, family: EndpointFamily) -> None:
        with self._lock:
            window = self._windows[family]
            now = self._clock()
            if now >= window.daily_reset_at:
                hourly, daily = _PUBLISHED[family]
                window.hourly_remaining = hourly
                window.daily_remaining = daily
                window.reset_at = now + 3600
                window.daily_reset_at = now + 86400
            if now >= window.reset_at:
                hourly, _daily = _PUBLISHED[family]
                window.hourly_remaining = hourly
                window.reset_at = now + 3600
            if window.hourly_remaining <= 0 or window.daily_remaining <= 0:
                raise RuntimeError(f"DNSE {family.value} rate budget exhausted locally")
            window.hourly_remaining -= 1
            window.daily_remaining -= 1

    def update(self, family: EndpointFamily, headers: Mapping[str, str]) -> None:
        normalized = {key.lower(): value for key, value in headers.items()}
        with self._lock:
            window = self._windows[family]
            remaining = _nonnegative_int(
                normalized.get("x-ratelimit-remaining")
                or normalized.get("ratelimit-remaining")
            )
            daily = _nonnegative_int(normalized.get("x-ratelimit-daily-remaining"))
            reset = _nonnegative_float(
                normalized.get("x-ratelimit-reset") or normalized.get("ratelimit-reset")
            )
            if remaining is not None:
                window.hourly_remaining = min(window.hourly_remaining, remaining)
            if daily is not None:
                window.daily_remaining = min(window.daily_remaining, daily)
            if reset is not None:
                window.reset_at = reset if reset > self._clock() else self._clock() + reset

    def remaining(self, family: EndpointFamily) -> int:
        with self._lock:
            window = self._windows[family]
            return min(window.hourly_remaining, window.daily_remaining)


def _nonnegative_int(value: str | None) -> int | None:
    try:
        parsed = int(value) if value is not None else None
    except ValueError:
        return None
    return parsed if parsed is not None and parsed >= 0 else None


def _nonnegative_float(value: str | None) -> float | None:
    try:
        parsed = float(value) if value is not None else None
    except ValueError:
        return None
    return parsed if parsed is not None and parsed >= 0 else None
