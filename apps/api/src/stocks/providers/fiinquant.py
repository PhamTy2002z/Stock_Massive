"""FiinQuant hot-market adapter for the bounded internal universe."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from time import monotonic
from typing import Any

import pandas as pd
from zoneinfo import ZoneInfo

from .contracts import (
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
)
from ..shared import validate_symbol

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
MAX_FREE_SYMBOLS = 33
MARKET_FIELDS = ["open", "high", "low", "close", "volume"]


class FiinQuantProviderError(RuntimeError):
    """Safe provider error that never contains account credentials."""


class FiinQuantCircuitOpen(FiinQuantProviderError):
    """Raised while calls are paused after repeated provider failures."""


class ProviderCircuitBreaker:
    """Small in-process breaker protecting the collector from retry storms."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: int = 60,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if failure_threshold < 1 or cooldown_seconds < 1:
            raise ValueError("circuit breaker limits must be positive")
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self.failure_count = 0
        self.opened_at: float | None = None

    def allow(self) -> None:
        if self.opened_at is None:
            return
        if self.clock() - self.opened_at >= self.cooldown_seconds:
            self.failure_count = 0
            self.opened_at = None
            return
        raise FiinQuantCircuitOpen("FiinQuant circuit is temporarily open")

    def record_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.opened_at = self.clock()


def _default_session_factory(username: str, password: str) -> Any:
    try:
        from FiinQuantX import FiinSession
    except ImportError as exc:  # pragma: no cover - exercised in built image
        raise FiinQuantProviderError("FiinQuantX is not installed") from exc
    return FiinSession(username=username, password=password).login()


class FiinQuantMarketProvider:
    """Fetch and normalize the latest two one-minute candles per symbol."""

    source = ProviderSource.FIINQUANT

    def __init__(
        self,
        username: str,
        password: str,
        session_factory: Callable[[str, str], Any] = _default_session_factory,
        circuit_breaker: ProviderCircuitBreaker | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not username or not password:
            raise FiinQuantProviderError("FiinQuant credentials are not configured")
        self._username = username
        self._password = password
        self._session_factory = session_factory
        self._circuit = circuit_breaker or ProviderCircuitBreaker()
        self._now = now
        self._client: Any | None = None

    def fetch_market(self, symbols: Sequence[str]) -> Sequence[MarketSnapshot]:
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        if not normalized:
            return ()
        if len(normalized) > MAX_FREE_SYMBOLS:
            raise ValueError(f"FiinQuant free universe is limited to {MAX_FREE_SYMBOLS} symbols")

        self._circuit.allow()
        try:
            client = self._get_client()
            frame = client.Fetch_Trading_Data(
                realtime=False,
                tickers=list(normalized),
                fields=MARKET_FIELDS,
                adjusted=False,
                by="1m",
                period=2,
                lasted=True,
            ).get_data()
            snapshots = self._normalize_frame(frame, normalized)
        except FiinQuantCircuitOpen:
            raise
        except FiinQuantProviderError:
            self._circuit.record_failure()
            raise
        except Exception as exc:
            self._circuit.record_failure()
            raise FiinQuantProviderError("FiinQuant market fetch failed") from exc

        self._circuit.record_success()
        return snapshots

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = self._session_factory(self._username, self._password)
            except Exception as exc:
                raise FiinQuantProviderError("FiinQuant login failed") from exc
        return self._client

    def _normalize_frame(
        self,
        frame: pd.DataFrame,
        requested_symbols: Sequence[str],
    ) -> tuple[MarketSnapshot, ...]:
        if frame is None or frame.empty:
            return ()

        columns = {str(column).lower(): column for column in frame.columns}
        required = {"ticker", "timestamp", "close"}
        missing = required - columns.keys()
        if missing:
            raise FiinQuantProviderError(
                f"FiinQuant response is missing fields: {', '.join(sorted(missing))}"
            )

        working = frame.rename(columns={value: key for key, value in columns.items()}).copy()
        working["ticker"] = working["ticker"].astype(str).str.upper()
        working = working[working["ticker"].isin(requested_symbols)]
        observed_at = self._now()
        snapshots: list[MarketSnapshot] = []

        for symbol in requested_symbols:
            rows = working[working["ticker"] == symbol].copy()
            if rows.empty:
                continue
            rows["timestamp"] = pd.to_datetime(rows["timestamp"], errors="coerce")
            rows = rows.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
            if rows.empty:
                continue

            latest = rows.iloc[-1]
            previous_close = rows.iloc[-2]["close"] if len(rows) > 1 else None
            effective_at = latest["timestamp"].to_pydatetime()
            if effective_at.tzinfo is None:
                effective_at = effective_at.replace(tzinfo=VN_TZ)

            close = _optional_float(latest.get("close"))
            reference = _optional_float(previous_close)
            change_pct = None
            if close is not None and reference not in (None, 0):
                change_pct = (close - reference) / reference * 100

            snapshots.append(
                MarketSnapshot(
                    symbol=symbol,
                    metadata=SnapshotMetadata(
                        source=self.source,
                        effective_at=effective_at,
                        observed_at=observed_at,
                    ),
                    last_price=close,
                    reference_price=reference,
                    open_price=_optional_float(latest.get("open")),
                    high_price=_optional_float(latest.get("high")),
                    low_price=_optional_float(latest.get("low")),
                    change_pct=change_pct,
                    volume=_optional_int(latest.get("volume")),
                )
            )

        return tuple(snapshots)


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
