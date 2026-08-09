"""FiinQuant hot-market adapter for the bounded internal universe."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from datetime import date, datetime, time, timedelta, timezone
from time import monotonic
from typing import Any

import pandas as pd
from pydantic import ValidationError
from zoneinfo import ZoneInfo

from .contracts import (
    MarketSnapshot,
    ProviderSource,
    SnapshotMetadata,
)
from ..shared import validate_symbol

logger = logging.getLogger(__name__)

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

# Two sessions are needed for the reference price. The window is wide enough to
# clear Tet, which closes the exchange for around nine days running with
# weekends on either side. Widening it costs nothing: it is still one call.
HISTORY_LOOKBACK_DAYS = 30

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
    ``get_ceilingfloor`` carries the day's permitted band.

    A malformed response from any of the three is an error, because a snapshot
    missing money fields is worse than no snapshot. A well-formed response that
    simply has no row for a symbol is not: that symbol keeps whatever the other
    calls gave it, and one unusable symbol never costs the rest of the batch.
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
        self._session: Any | None = None

    def fetch_market(self, symbols: Sequence[str]) -> Sequence[MarketSnapshot]:
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        if not normalized:
            return ()
        if len(normalized) > MAX_BATCH_SYMBOLS:
            raise ValueError(f"a FiinQuant batch is limited to {MAX_BATCH_SYMBOLS} symbols")

        self._circuit.allow()
        try:
            snapshots = self._guarded(
                lambda: self._fetch_batch(normalized),
                "FiinQuant market fetch failed",
            )
        except FiinQuantCircuitOpen:
            raise
        except FiinQuantProviderError:
            self._circuit.record_failure()
            raise

        self._circuit.record_success()
        return snapshots

    def _fetch_batch(self, symbols: Sequence[str]) -> tuple[MarketSnapshot, ...]:
        session = self._get_session()
        tickers = list(symbols)
        from_date = str(
            self._now().astimezone(VN_TZ).date() - timedelta(days=HISTORY_LOOKBACK_DAYS)
        )

        candles = session.Fetch_Trading_Data(
            realtime=False,
            tickers=tickers,
            # A list, not a tuple: the library indexes into this argument.
            fields=MARKET_FIELDS,
            adjusted=False,
            by="1d",
            from_date=from_date,
        ).get_data()
        price_statistics = session.PriceStatistics()
        overview = price_statistics.get_overview(
            tickers=tickers,
            time_filter="Daily",
            from_date=from_date,
        )
        ceiling_floor = price_statistics.get_ceilingfloor(
            tickers=tickers,
            from_date=from_date,
        )

        return self._normalize(candles, overview, ceiling_floor, symbols)

    def _get_session(self) -> Any:
        if self._session is None:
            self._session = self._guarded(
                lambda: self._session_factory(self._username, self._password),
                "FiinQuant login failed",
            )
        return self._session

    @staticmethod
    def _guarded(call: Callable[[], Any], message: str) -> Any:
        """Run an upstream call, keeping its exception text out of ours entirely.

        A failed login has been seen to echo the credentials back. ``raise ...
        from None`` would still leave that text on ``__context__``, so the new
        error is raised outside the handler and only the exception type name
        survives.
        """
        failure: str | None = None
        try:
            return call()
        except FiinQuantProviderError:
            raise
        except Exception as exc:
            failure = type(exc).__name__
        raise FiinQuantProviderError(f"{message} ({failure})")

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
        overview_by_symbol = _session_row_by_symbol(
            _prepare(overview, OVERVIEW_FIELDS, requested_symbols),
            "overview",
        )
        band_by_symbol = _session_row_by_symbol(
            _prepare(ceiling_floor, CEILING_FLOOR_FIELDS, requested_symbols),
            "ceiling/floor",
        )

        observed_at = self._now()
        snapshots: list[MarketSnapshot] = []

        for symbol in requested_symbols:
            latest, previous = _last_two_sessions(sessions, symbol)
            if latest is None:
                continue

            session_date = latest["timestamp"].date()
            snapshot = _build_snapshot(
                symbol=symbol,
                source=self.source,
                observed_at=observed_at,
                latest=latest,
                previous=previous,
                # Statistics are only trusted for the session being described:
                # the three calls are not in lockstep, and last session's market
                # cap silently stamped onto today would never be noticed.
                overview=_row_for_date(overview_by_symbol.get(symbol), session_date),
                band=_row_for_date(band_by_symbol.get(symbol), session_date),
            )
            if snapshot is None:
                continue
            snapshots.append(snapshot)

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


def _build_snapshot(
    symbol: str,
    source: ProviderSource,
    observed_at: datetime,
    latest: pd.Series,
    previous: pd.Series | None,
    overview: pd.Series | None,
    band: pd.Series | None,
) -> MarketSnapshot | None:
    """Assemble one snapshot, or None when this symbol's row cannot be trusted.

    A suspended or freshly listed symbol comes back with zeroed prices, which
    the MarketSnapshot contract rejects. That is one unusable symbol, not a
    broken response, so it is dropped here rather than raised — otherwise a
    single halted ticker would cost the whole batch its snapshots.
    """
    close = _optional_float(latest.get("close"))
    reference = _optional_float(previous.get("close")) if previous is not None else None
    change_pct = None
    if close is not None and reference not in (None, 0):
        change_pct = (close - reference) / reference * 100

    try:
        return MarketSnapshot(
            symbol=symbol,
            metadata=SnapshotMetadata(
                source=source,
                effective_at=_as_aware(latest["timestamp"]),
                observed_at=observed_at,
            ),
            last_price=close,
            reference_price=reference,
            open_price=_optional_float(latest.get("open")),
            high_price=_optional_float(latest.get("high")),
            low_price=_optional_float(latest.get("low")),
            ceiling_price=_cell(band, "ceilingprice"),
            floor_price=_cell(band, "floorprice"),
            change_pct=change_pct,
            volume=_optional_int(latest.get("volume")),
            total_value_vnd=_optional_float(latest.get("value")),
            active_buy_volume=_optional_int(latest.get("bu")),
            active_sell_volume=_optional_int(latest.get("sd")),
            foreign_buy_value_vnd=_optional_float(latest.get("fb")),
            foreign_sell_value_vnd=_optional_float(latest.get("fs")),
            foreign_net_value_vnd=_optional_float(latest.get("fn")),
            market_cap_vnd=_cell(overview, "marketcap"),
        )
    except ValidationError as exc:
        logger.warning("Skipping unusable FiinQuant row for %s: %s", symbol, exc)
        return None


def _cell(row: pd.Series | None, field: str) -> float | None:
    if row is None:
        return None
    return _optional_float(row.get(field))


def _session_row_by_symbol(frame: pd.DataFrame, label: str) -> dict[str, pd.Series]:
    """Keep the most recent row per symbol, which describes the latest session."""
    if frame.empty:
        # Not fatal — the candles still carry the capability — but a whole
        # statistics call coming back empty is worth seeing in the log.
        logger.warning("FiinQuant returned no %s rows for this batch", label)
        return {}
    return {
        str(symbol): rows.iloc[-1]
        for symbol, rows in frame.groupby("ticker", sort=False)
    }


def _row_for_date(row: pd.Series | None, session_date: date) -> pd.Series | None:
    if row is None or row["timestamp"].date() != session_date:
        return None
    return row


def _last_two_sessions(
    frame: pd.DataFrame,
    symbol: str,
) -> tuple[pd.Series | None, pd.Series | None]:
    """Return this session and the one before it, collapsing same-day rows.

    Asked for daily bars during a session, the provider returns two rows for
    today: the consolidated bar stamped midnight, plus a live one stamped now.
    The midnight row is the one whose volume and value were measured to match
    ``get_overview`` exactly, so it is preferred wherever a date has both. That
    also leaves one row per date, so the previous session is a real previous day
    rather than today seen twice.
    """
    if frame.empty:
        return None, None
    rows = frame[(frame["ticker"] == symbol) & frame["close"].notna()]
    if rows.empty:
        return None, None

    sessions = [
        _consolidated_bar(day_rows)
        for _, day_rows in rows.groupby(rows["timestamp"].dt.date, sort=True)
    ]
    previous = sessions[-2] if len(sessions) > 1 else None
    return sessions[-1], previous


def _consolidated_bar(day_rows: pd.DataFrame) -> pd.Series:
    at_midnight = day_rows[day_rows["timestamp"].dt.time == time(0, 0)]
    return at_midnight.iloc[-1] if not at_midnight.empty else day_rows.iloc[-1]


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
