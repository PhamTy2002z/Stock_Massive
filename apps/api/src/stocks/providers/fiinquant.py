"""FiinQuant hot-market adapter for the bounded internal universe."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
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

# The published free-tier ceiling of 33 symbols applies to the realtime stream
# only: historical calls were measured good at 110 symbols in one request. The
# bound here is the largest batch the collector is allowed to commit to.
MAX_BATCH_SYMBOLS = 100

# Everything the free tier returns for a daily bar. bu/sd are quantities while
# fb/fs/fn are money — see MarketSnapshot for why the two never share a name.
MARKET_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
    "bu",
    "sd",
    "fb",
    "fs",
    "fn",
]

# Two sessions are needed for the reference price, and a holiday weekend can
# push the previous one back several calendar days.
HISTORY_LOOKBACK_DAYS = 10

OVERVIEW_FIELDS = ("ticker", "timestamp", "marketcap")
CEILING_FLOOR_FIELDS = ("ticker", "timestamp", "ceilingprice", "floorprice")


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


def ensure_ca_bundle() -> str:
    """Point the default SSL context at certifi before FiinQuantX opens a session.

    FiinQuantX swallows ``CERTIFICATE_VERIFY_FAILED`` and returns an empty frame
    instead of raising, so a missing CA bundle looks exactly like a market with
    no data. Every way of ending up without a usable bundle is raised here
    instead, because a diagnosable error beats a market that appears closed.
    """
    existing = os.environ.get("SSL_CERT_FILE")
    if existing:
        if not os.path.isfile(existing):
            raise FiinQuantProviderError(
                f"SSL_CERT_FILE points at a CA bundle that does not exist: {existing}"
            )
        return existing
    try:
        import certifi
    except ImportError as exc:  # pragma: no cover - certifi ships with requests
        raise FiinQuantProviderError(
            "no CA bundle available: certifi is not installed and "
            "SSL_CERT_FILE is unset"
        ) from exc
    bundle = certifi.where()
    if not os.path.isfile(bundle):  # pragma: no cover - broken certifi install
        raise FiinQuantProviderError(
            f"certifi reported a CA bundle that does not exist: {bundle}"
        )
    os.environ["SSL_CERT_FILE"] = bundle
    return bundle


def _default_session_factory(username: str, password: str) -> Any:
    ensure_ca_bundle()
    try:
        from FiinQuantX import FiinSession
    except ImportError as exc:  # pragma: no cover - exercised in built image
        raise FiinQuantProviderError("FiinQuantX is not installed") from exc
    return FiinSession(username=username, password=password).login()


class FiinQuantMarketProvider:
    """Turn one batched end-of-day read into one MarketSnapshot per symbol.

    A session is assembled from three calls: daily candles carry price, volume,
    value and both flow pairs; ``get_overview`` carries market cap; and
    ``get_ceilingfloor`` carries the day's permitted band. Only the candles are
    load-bearing — a symbol absent from the statistics keeps its market fields
    and leaves the statistics ones empty.
    """

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
        if len(normalized) > MAX_BATCH_SYMBOLS:
            raise ValueError(f"a FiinQuant batch is limited to {MAX_BATCH_SYMBOLS} symbols")

        self._circuit.allow()
        try:
            snapshots = self._fetch_batch(normalized)
        except FiinQuantCircuitOpen:
            raise
        except FiinQuantProviderError:
            self._circuit.record_failure()
            raise
        except Exception as exc:
            self._circuit.record_failure()
            # The upstream message is dropped, not wrapped: it has been seen to
            # echo the credentials back.
            raise FiinQuantProviderError(
                f"FiinQuant market fetch failed ({type(exc).__name__})"
            ) from None

        self._circuit.record_success()
        return snapshots

    def _fetch_batch(self, symbols: Sequence[str]) -> tuple[MarketSnapshot, ...]:
        client = self._get_client()
        tickers = list(symbols)
        from_date = str(
            self._now().astimezone(VN_TZ).date() - timedelta(days=HISTORY_LOOKBACK_DAYS)
        )

        candles = client.Fetch_Trading_Data(
            realtime=False,
            tickers=tickers,
            fields=MARKET_FIELDS,
            adjusted=False,
            by="1d",
            from_date=from_date,
        ).get_data()
        statistics = client.PriceStatistics()
        overview = statistics.get_overview(
            tickers=tickers,
            time_filter="Daily",
            from_date=from_date,
        )
        ceiling_floor = statistics.get_ceilingfloor(
            tickers=tickers,
            from_date=from_date,
        )

        return self._normalize(candles, overview, ceiling_floor, symbols)

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = self._session_factory(self._username, self._password)
            except Exception as exc:
                raise FiinQuantProviderError("FiinQuant login failed") from exc
        return self._client

    def _normalize(
        self,
        candles: pd.DataFrame,
        overview: pd.DataFrame,
        ceiling_floor: pd.DataFrame,
        requested_symbols: Sequence[str],
    ) -> tuple[MarketSnapshot, ...]:
        if candles is None or getattr(candles, "empty", True):
            # This is the documented silent-failure signature of the library:
            # a rejected certificate comes back as an empty frame, not an error.
            raise FiinQuantProviderError(
                "FiinQuant returned no market data for any requested symbol"
            )

        sessions = _prepare(
            candles,
            ("ticker", "timestamp", *MARKET_FIELDS),
            requested_symbols,
        )
        market_cap = _latest_row_by_symbol(
            _prepare(overview, OVERVIEW_FIELDS, requested_symbols)
        )
        band = _latest_row_by_symbol(
            _prepare(ceiling_floor, CEILING_FLOOR_FIELDS, requested_symbols)
        )

        observed_at = self._now()
        snapshots: list[MarketSnapshot] = []

        for symbol in requested_symbols:
            latest, previous = _last_two_sessions(sessions, symbol)
            if latest is None:
                continue

            close = _optional_float(latest.get("close"))
            reference = _optional_float(previous.get("close")) if previous is not None else None
            change_pct = None
            if close is not None and reference not in (None, 0):
                change_pct = (close - reference) / reference * 100

            statistics = market_cap.get(symbol)
            limits = band.get(symbol)
            snapshots.append(
                MarketSnapshot(
                    symbol=symbol,
                    metadata=SnapshotMetadata(
                        source=self.source,
                        effective_at=_as_aware(latest["timestamp"]),
                        observed_at=observed_at,
                    ),
                    last_price=close,
                    reference_price=reference,
                    open_price=_optional_float(latest.get("open")),
                    high_price=_optional_float(latest.get("high")),
                    low_price=_optional_float(latest.get("low")),
                    ceiling_price=_optional_float(
                        limits.get("ceilingprice") if limits is not None else None
                    ),
                    floor_price=_optional_float(
                        limits.get("floorprice") if limits is not None else None
                    ),
                    change_pct=change_pct,
                    volume=_optional_int(latest.get("volume")),
                    total_value_vnd=_optional_float(latest.get("value")),
                    active_buy_volume=_optional_int(latest.get("bu")),
                    active_sell_volume=_optional_int(latest.get("sd")),
                    foreign_buy_value_vnd=_optional_float(latest.get("fb")),
                    foreign_sell_value_vnd=_optional_float(latest.get("fs")),
                    foreign_net_value_vnd=_optional_float(latest.get("fn")),
                    market_cap_vnd=_optional_float(
                        statistics.get("marketcap") if statistics is not None else None
                    ),
                )
            )

        return tuple(snapshots)


def _prepare(
    frame: pd.DataFrame | None,
    required_fields: Sequence[str],
    requested_symbols: Sequence[str],
) -> pd.DataFrame:
    """Lower-case the columns, prove the fields arrived, keep the asked-for rows.

    The two ``PriceStatistics`` calls disagree on capitalization with each other
    and with the candle frame, so case is normalized before anything is read.
    """
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame(columns=list(required_fields))

    columns = {str(column).lower(): column for column in frame.columns}
    missing = set(required_fields) - columns.keys()
    if missing:
        raise FiinQuantProviderError(
            f"FiinQuant response is missing fields: {', '.join(sorted(missing))}"
        )

    working = frame.rename(columns={value: key for key, value in columns.items()}).copy()
    working = working[list(required_fields)]
    working["ticker"] = working["ticker"].astype(str).str.upper()
    working["timestamp"] = pd.to_datetime(working["timestamp"], errors="coerce")
    working = working.dropna(subset=["timestamp"])
    return working[working["ticker"].isin(list(requested_symbols))].sort_values("timestamp")


def _latest_row_by_symbol(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Keep only the most recent row per symbol, which is the current session."""
    if frame.empty:
        return {}
    return {
        str(symbol): rows.iloc[-1]
        for symbol, rows in frame.groupby("ticker", sort=False)
    }


def _last_two_sessions(
    frame: pd.DataFrame,
    symbol: str,
) -> tuple[pd.Series | None, pd.Series | None]:
    """Return this session and the one before it, collapsing same-day rows.

    Asked for daily bars during a session, the provider returns both a bar
    stamped midnight and a live bar stamped now. Grouping by calendar date and
    keeping the newest row per date leaves one row per session, so the previous
    session is a real previous day rather than the same day seen twice.
    """
    if frame.empty:
        return None, None
    rows = frame[(frame["ticker"] == symbol) & frame["close"].notna()]
    if rows.empty:
        return None, None
    sessions = [
        day_rows.iloc[-1]
        for _, day_rows in rows.groupby(rows["timestamp"].dt.date, sort=True)
    ]
    return sessions[-1], sessions[-2] if len(sessions) > 1 else None


def _as_aware(value: Any) -> datetime:
    moment = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    if moment.tzinfo is None:
        return moment.replace(tzinfo=VN_TZ)
    return moment


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
