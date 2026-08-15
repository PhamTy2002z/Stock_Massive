"""FiinQuant adapters for the bounded internal universe.

One adapter per capability — market and valuation — over a shared login,
circuit breaker and error-hygiene rule.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from datetime import date, datetime, time, timedelta, timezone
from time import monotonic
from typing import Any

import pandas as pd
from pydantic import ValidationError

from .contracts import (
    MARKET_SCHEMA_VERSION,
    BatchTooLarge,
    MarketIndexSnapshot,
    MarketSnapshot,
    PriceBasis,
    ProviderSource,
    SnapshotMetadata,
    ValuationSnapshot,
)
from .normalize import (
    VN_TZ,
    lower_cased_columns,
    missing_fields,
    normalized_symbols,
    optional_float,
    optional_int,
)

logger = logging.getLogger(__name__)

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

# Every candle call this adapter makes passes ``adjusted=MARKET_ADJUSTED``, so
# every session it writes says so on the row. The two constants belong together
# and move together: flipping the flag without the basis would stamp rescaled
# prices as exchange-published ones, and nothing downstream could tell.
MARKET_ADJUSTED = False
MARKET_PRICE_BASIS = PriceBasis.RAW

# What a daily index bar is made of, and it is deliberately shorter than
# MARKET_FIELDS. An index has no foreign split and no active buy/sell
# decomposition — asking for bu/sd/fb/fs/fn would either fail the field check or,
# worse, come back zeroed and be stored as a measurement of a flow that does not
# exist for a composite.
INDEX_FIELDS = ["open", "high", "low", "close", "volume", "value"]

OVERVIEW_FIELDS = ("ticker", "timestamp", "marketcap")
CEILING_FLOOR_FIELDS = ("ticker", "timestamp", "ceilingprice", "floorprice")

# Valuation arrives as its own daily series: one row per symbol per session.
VALUATION_FIELDS = ("ticker", "timestamp", "pe", "pb")


GATEWAY_TIMEOUT_STATUS = 504

# What a 504 looks like once it has been through a layer that kept only the
# text. The word "gateway" has to be there as well as the code: a message that
# merely contains those three digits is some other failure, and reading it as an
# oversized batch would have the caller retrying an outage in halves. The
# provider's text is read here and nowhere else — it is never repeated back.
GATEWAY_TIMEOUT_MARKERS = ("504", "time-out", "timeout")


class FiinQuantProviderError(RuntimeError):
    """Safe provider error that never contains account credentials."""


class FiinQuantCircuitOpen(FiinQuantProviderError):
    """Raised while calls are paused after repeated provider failures."""


class FiinQuantBatchTooLarge(FiinQuantProviderError, BatchTooLarge):
    """The gateway gave up on this request; the same symbols may fit in halves.

    Both parents on purpose: a caller that only knows this provider still
    catches it as one of its errors, while the collector catches the neutral
    ``BatchTooLarge`` without having to know which provider it came from.

    It still counts against the circuit breaker. Halving survives that because
    a batch that succeeds resets the count, and a gateway that keeps timing out
    however small the batch gets is an outage — which is exactly when the caller
    should stop rather than retry a hundred symbols one at a time.
    """


def _is_gateway_timeout(exc: BaseException) -> bool:
    """Recognise a 504 from the status code, or from the text if that is all there is."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == GATEWAY_TIMEOUT_STATUS:
        return True
    text = str(exc).lower()
    return "gateway" in text and any(
        marker in text for marker in GATEWAY_TIMEOUT_MARKERS
    )


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


def shared_session_factory(
    factory: Callable[[str, str], Any] = _default_session_factory,
) -> Callable[[str, str], Any]:
    """Return a factory that logs in once and hands the same session to everyone.

    The free tier grants a single concurrent connection, so two adapters each
    logging in for themselves is one of them being disconnected mid-cycle. Every
    adapter built for one account shares one of these.
    """
    session: list[Any] = []

    def login(username: str, password: str) -> Any:
        if not session:
            session.append(factory(username, password))
        return session[0]

    return login


class FiinQuantProviderBase:
    """Session handling, circuit protection and error hygiene shared by adapters.

    Each capability gets its own adapter because each reads a different set of
    provider calls, but they all sit behind the same login and the same rule
    that no upstream text is ever repeated back to the caller.
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

    @staticmethod
    def _batch(symbols: Sequence[str]) -> tuple[str, ...]:
        normalized = normalized_symbols(symbols)
        if len(normalized) > MAX_BATCH_SYMBOLS:
            raise ValueError(f"a FiinQuant batch is limited to {MAX_BATCH_SYMBOLS} symbols")
        return normalized

    def _protected(self, call: Callable[[], Any], message: str) -> Any:
        """Run one upstream round trip under the breaker, counting its outcome."""
        # Outside the try: an open circuit is the breaker working, not a fresh
        # failure, and counting it would keep the cooldown from ever expiring.
        self._circuit.allow()
        try:
            result = self._guarded(call, message)
        except FiinQuantProviderError:
            self._circuit.record_failure()
            raise

        self._circuit.record_success()
        return result

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
        oversized = False
        try:
            return call()
        except FiinQuantProviderError:
            raise
        except Exception as exc:
            failure = type(exc).__name__
            oversized = _is_gateway_timeout(exc)
        if oversized:
            raise FiinQuantBatchTooLarge(f"{message} (gateway timeout)")
        raise FiinQuantProviderError(f"{message} ({failure})")

    def _today(self) -> date:
        return self._now().astimezone(VN_TZ).date()


class FiinQuantMarketProvider(FiinQuantProviderBase):
    """Turn one batched end-of-day read into one MarketSnapshot per symbol.

    A session is assembled from three calls: daily candles carry price, volume,
    value and both flow pairs; ``get_overview`` carries market cap; and
    ``get_ceilingfloor`` carries the day's permitted band.

    A malformed response from any of the three is an error, because a snapshot
    missing money fields is worse than no snapshot. A well-formed response that
    simply has no row for a symbol is not: that symbol keeps whatever the other
    calls gave it, and one unusable symbol never costs the rest of the batch.
    """

    def fetch_market(self, symbols: Sequence[str]) -> Sequence[MarketSnapshot]:
        normalized = self._batch(symbols)
        if not normalized:
            return ()
        return self._protected(
            lambda: self._fetch_batch(normalized),
            "FiinQuant market fetch failed",
        )

    def fetch_market_history(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> Sequence[MarketSnapshot]:
        """Read every session in a window, for the one-time history load.

        ``fetch_market`` answers with the session that just closed; this answers
        with all of them, which is what a multi-year chart is made of. The frame
        and the normalization are the same — only how much of it is kept differs.

        The two ``PriceStatistics`` calls are not made. They answer for one
        session, and a load that stamped today's market cap or price band onto a
        session from 2019 would be inventing figures that look measured.
        """
        if from_date > to_date:
            raise ValueError("from_date cannot be later than to_date")
        normalized = self._batch([symbol])
        if not normalized:
            return ()

        return self._protected(
            lambda: self._fetch_history(normalized[0], from_date, to_date),
            "FiinQuant market history fetch failed",
        )

    def _fetch_history(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> tuple[MarketSnapshot, ...]:
        candles = self._get_session().Fetch_Trading_Data(
            realtime=False,
            tickers=[symbol],
            fields=MARKET_FIELDS,
            adjusted=MARKET_ADJUSTED,
            by="1d",
            from_date=str(from_date),
            to_date=str(to_date),
        ).get_data()

        _require_populated(candles, "market history")
        sessions = _prepare(candles, ("ticker", "timestamp", *MARKET_FIELDS), (symbol,))
        observed_at = self._now()

        snapshots: list[MarketSnapshot] = []
        previous: pd.Series | None = None
        for session in _one_row_per_session(sessions, symbol):
            snapshot = _build_snapshot(
                symbol=symbol,
                source=self.source,
                observed_at=observed_at,
                latest=session,
                previous=previous,
                overview=None,
                band=None,
            )
            # A session the contract refuses is skipped, but it still stands as
            # the reference for the next one: the market moved from that close
            # whether or not this system could store it.
            previous = session
            if snapshot is not None:
                snapshots.append(snapshot)

        return tuple(snapshots)

    def _fetch_batch(self, symbols: Sequence[str]) -> tuple[MarketSnapshot, ...]:
        session = self._get_session()
        tickers = list(symbols)
        from_date = str(self._today() - timedelta(days=HISTORY_LOOKBACK_DAYS))

        candles = session.Fetch_Trading_Data(
            realtime=False,
            tickers=tickers,
            # A list, not a tuple: the library indexes into this argument.
            fields=MARKET_FIELDS,
            adjusted=MARKET_ADJUSTED,
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

    def _normalize(
        self,
        candles: pd.DataFrame,
        overview: pd.DataFrame,
        ceiling_floor: pd.DataFrame,
        requested_symbols: Sequence[str],
    ) -> tuple[MarketSnapshot, ...]:
        _require_populated(candles, "market")

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


class FiinQuantMarketIndexProvider(FiinQuantProviderBase):
    """Read a market index's own daily series, as a series of index levels.

    The same candle call the market adapter makes, over an index code rather
    than a ticker, and with three deliberate subtractions: the shorter field
    list above, no ``PriceStatistics`` calls at all — an index has neither a
    band nor a market capitalisation, so there is nothing those two could answer
    — and a contract with no room for either.

    History only. There is no ``fetch_index`` answering "the index right now":
    the stored series exists to be regressed against a symbol's stored window,
    and a current level nothing else is dated against would be the live read
    ``docs/specs/0003`` §13 forbids on a serving path.
    """

    def fetch_index_history(
        self,
        index: str,
        from_date: date,
        to_date: date,
    ) -> Sequence[MarketIndexSnapshot]:
        if from_date > to_date:
            raise ValueError("from_date cannot be later than to_date")
        code = index.strip().upper()
        if not code:
            return ()

        return self._protected(
            lambda: self._fetch_index_history(code, from_date, to_date),
            "FiinQuant market index history fetch failed",
        )

    def _fetch_index_history(
        self,
        index: str,
        from_date: date,
        to_date: date,
    ) -> tuple[MarketIndexSnapshot, ...]:
        candles = self._get_session().Fetch_Trading_Data(
            realtime=False,
            tickers=[index],
            fields=INDEX_FIELDS,
            # Passed for the same reason the market call passes it: the flag and
            # the basis written below move together. An index is not adjusted for
            # anything either way, so the two agree trivially — but a call that
            # quietly asked for something else would still be saying `raw` on the
            # row.
            adjusted=MARKET_ADJUSTED,
            by="1d",
            from_date=str(from_date),
            to_date=str(to_date),
        ).get_data()

        _require_populated(candles, "market index history")
        sessions = _prepare(candles, ("ticker", "timestamp", *INDEX_FIELDS), (index,))
        observed_at = self._now()

        snapshots: list[MarketIndexSnapshot] = []
        previous: pd.Series | None = None
        for session in _one_row_per_session(sessions, index):
            snapshot = _build_index_snapshot(
                index=index,
                source=self.source,
                observed_at=observed_at,
                latest=session,
                previous=previous,
            )
            # A session the contract refuses still stands as the level the next
            # one moved from, exactly as in the market history.
            previous = session
            if snapshot is not None:
                snapshots.append(snapshot)

        return tuple(snapshots)


class FiinQuantValuationProvider(FiinQuantProviderBase):
    """Turn one batched read of the ratio series into a snapshot per session.

    ``get_stock_valuation`` answers with one row per symbol per session, so a
    single call covers the whole requested window for the whole batch. The
    window is required rather than defaulted: the collector asks for the session
    that just closed and a backfill asks for a stretch of history, and a default
    would quietly hand one of them the other's window.

    A malformed response is an error, but a session the provider has no ratios
    for is not — an unvalued symbol is a normal thing in this market, and it
    never costs the rest of the batch its snapshots.
    """

    def fetch_valuation(
        self,
        symbols: Sequence[str],
        from_date: date,
        to_date: date,
    ) -> Sequence[ValuationSnapshot]:
        if from_date > to_date:
            raise ValueError("from_date cannot be later than to_date")
        normalized = self._batch(symbols)
        if not normalized:
            return ()

        return self._protected(
            lambda: self._fetch_ratio_series(normalized, from_date, to_date),
            "FiinQuant valuation fetch failed",
        )

    def _fetch_ratio_series(
        self,
        symbols: Sequence[str],
        from_date: date,
        to_date: date,
    ) -> tuple[ValuationSnapshot, ...]:
        session = self._get_session()
        ratios = session.MarketDepth().get_stock_valuation(
            tickers=list(symbols),
            from_date=str(from_date),
            to_date=str(to_date),
        )
        return self._to_snapshots(ratios, symbols)

    def _to_snapshots(
        self,
        ratios: pd.DataFrame,
        requested_symbols: Sequence[str],
    ) -> tuple[ValuationSnapshot, ...]:
        _require_populated(ratios, "valuation")

        sessions = _prepare(ratios, VALUATION_FIELDS, requested_symbols)
        observed_at = self._now()
        snapshots: list[ValuationSnapshot] = []

        for symbol in requested_symbols:
            for _, row in sessions[sessions["ticker"] == symbol].iterrows():
                snapshot = _build_valuation_snapshot(
                    symbol=symbol,
                    source=self.source,
                    observed_at=observed_at,
                    row=row,
                )
                if snapshot is None:
                    continue
                snapshots.append(snapshot)

        return tuple(snapshots)


def _require_populated(frame: pd.DataFrame | None, label: str) -> None:
    """Refuse a wholly empty response instead of reading it as an empty market.

    This is the documented silent-failure signature of the library: a rejected
    certificate comes back as an empty frame, not an error. Treating it as "no
    data" would make a broken connection indistinguishable from a quiet day.

    The cost is accepted deliberately: a batch where genuinely every symbol is
    unknown to the provider also raises. Per-symbol gaps are the normal case and
    are handled inside a well-formed frame, so a frame with nothing in it at all
    is far more likely to be the connection than the market.
    """
    if frame is None or getattr(frame, "empty", True):
        raise FiinQuantProviderError(
            f"FiinQuant returned no {label} data for any requested symbol"
        )


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

    working = lower_cased_columns(frame)
    missing = missing_fields(working, required_fields)
    if missing:
        raise FiinQuantProviderError(
            f"FiinQuant response is missing fields: {', '.join(missing)}"
        )

    working = working[list(required_fields)].copy()
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
    close = optional_float(latest.get("close"))
    reference = optional_float(previous.get("close")) if previous is not None else None
    change_pct = None
    if close is not None and reference not in (None, 0):
        change_pct = (close - reference) / reference * 100

    volume = optional_int(latest.get("volume"))
    active_buy, active_sell = _active_flow(latest, volume)

    try:
        return MarketSnapshot(
            symbol=symbol,
            metadata=SnapshotMetadata(
                source=source,
                effective_at=_session_start(latest["timestamp"]),
                observed_at=observed_at,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            # This adapter is the only code that knows which flag the call
            # carried, so it is the only code that may say what the prices mean.
            price_basis=MARKET_PRICE_BASIS,
            last_price=close,
            reference_price=reference,
            open_price=optional_float(latest.get("open")),
            high_price=optional_float(latest.get("high")),
            low_price=optional_float(latest.get("low")),
            ceiling_price=_cell(band, "ceilingprice"),
            floor_price=_cell(band, "floorprice"),
            change_pct=change_pct,
            volume=volume,
            total_value_vnd=optional_float(latest.get("value")),
            active_buy_volume=active_buy,
            active_sell_volume=active_sell,
            foreign_buy_value_vnd=optional_float(latest.get("fb")),
            foreign_sell_value_vnd=optional_float(latest.get("fs")),
            foreign_net_value_vnd=optional_float(latest.get("fn")),
            market_cap_vnd=_cell(overview, "marketcap"),
        )
    except ValidationError as exc:
        logger.warning("Skipping unusable FiinQuant row for %s: %s", symbol, exc)
        return None


def _build_index_snapshot(
    index: str,
    source: ProviderSource,
    observed_at: datetime,
    latest: pd.Series,
    previous: pd.Series | None,
) -> MarketIndexSnapshot | None:
    """Assemble one index session, or None when the row cannot be trusted.

    Dropped rather than raised for the same reason a suspended equity's row is:
    one unusable session is one day of the series, and a whole load abandoned
    over it would leave the benchmark short of the depth the field it feeds
    declares.

    ``change_pct`` is measured against the previous stored level rather than
    read from the provider, which is the same arithmetic the market history
    does. No ``reference_price`` is written: that field is the band's anchor and
    an index has no band.
    """
    close = optional_float(latest.get("close"))
    reference = optional_float(previous.get("close")) if previous is not None else None
    change_pct = None
    if close is not None and reference not in (None, 0):
        change_pct = (close - reference) / reference * 100

    try:
        return MarketIndexSnapshot(
            symbol=index,
            metadata=SnapshotMetadata(
                source=source,
                effective_at=_session_start(latest["timestamp"]),
                observed_at=observed_at,
                schema_version=MARKET_SCHEMA_VERSION,
            ),
            price_basis=MARKET_PRICE_BASIS,
            last_price=close,
            open_price=optional_float(latest.get("open")),
            high_price=optional_float(latest.get("high")),
            low_price=optional_float(latest.get("low")),
            change_pct=change_pct,
            volume=optional_int(latest.get("volume")),
            total_value_vnd=optional_float(latest.get("value")),
        )
    except ValidationError as exc:
        logger.warning("Skipping unusable FiinQuant index row for %s: %s", index, exc)
        return None


def _build_valuation_snapshot(
    symbol: str,
    source: ProviderSource,
    observed_at: datetime,
    row: pd.Series,
) -> ValuationSnapshot | None:
    """Assemble one session's ratios, or None when the session carries neither.

    The provider dates a row for every session it knows about, ratios or not, so
    a row with both blank is a symbol it does not value rather than a broken
    response. Recording it would store a date and nothing else. One ratio
    present is still worth keeping: the other is a genuine gap, not a guess.
    """
    provider_pe = optional_float(row.get("pe"))
    provider_pb = optional_float(row.get("pb"))
    if provider_pe is None and provider_pb is None:
        return None

    try:
        return ValuationSnapshot(
            symbol=symbol,
            metadata=SnapshotMetadata(
                source=source,
                effective_at=_session_start(row["timestamp"]),
                observed_at=observed_at,
            ),
            provider_pe=provider_pe,
            provider_pb=provider_pb,
        )
    except ValidationError as exc:
        logger.warning("Skipping unusable FiinQuant valuation row for %s: %s", symbol, exc)
        return None


def _active_flow(
    latest: pd.Series,
    volume: int | None,
) -> tuple[int | None, int | None]:
    """Read bu/sd, or report them absent when the provider has not split them yet.

    The session that just closed reaches the daily series before its active
    buy/sell decomposition does: both come back as exactly 0 against millions of
    matched shares. Stored as zeros they say nobody bought or sold actively all
    session, which is a claim about the market invented out of the provider's
    publishing clock.

    Both at once is the whole rule, and deliberately so. A session that matched
    nothing keeps its zeros, since there the pair is the answer rather than a
    gap. A lone zero keeps it too: no measurement distinguishes it from a symbol
    nobody bought actively that day, and blanking it would invent a gap as
    readily as the zeros invent a figure.
    """
    active_buy = optional_int(latest.get("bu"))
    active_sell = optional_int(latest.get("sd"))
    if active_buy == 0 and active_sell == 0 and volume:
        return None, None
    return active_buy, active_sell


def _cell(row: pd.Series | None, field: str) -> float | None:
    if row is None:
        return None
    return optional_float(row.get(field))


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


def _one_row_per_session(frame: pd.DataFrame, symbol: str) -> list[pd.Series]:
    """This symbol's sessions, oldest first, one row each.

    The provider can return two rows for the current session: the consolidated
    bar stamped midnight, plus a live one stamped at the last tick. The midnight
    row is the one whose volume and value were measured to match
    ``get_overview`` exactly, so it is preferred wherever a date has both. That
    also leaves one row per date, so a previous session is a real previous day
    rather than today seen twice.

    Hours after the close the live row can still be the only one there — the
    consolidation lands later, which is why the snapshot is dated by the day it
    traded and why an unpublished bu/sd is read as a gap.
    """
    if frame.empty:
        return []
    rows = frame[(frame["ticker"] == symbol) & frame["close"].notna()]
    if rows.empty:
        return []
    return [
        _consolidated_bar(day_rows)
        for _, day_rows in rows.groupby(rows["timestamp"].dt.date, sort=True)
    ]


def _last_two_sessions(
    frame: pd.DataFrame,
    symbol: str,
) -> tuple[pd.Series | None, pd.Series | None]:
    """Return this session and the one before it, for the daily read."""
    sessions = _one_row_per_session(frame, symbol)
    if not sessions:
        return None, None
    return sessions[-1], (sessions[-2] if len(sessions) > 1 else None)


def _consolidated_bar(day_rows: pd.DataFrame) -> pd.Series:
    at_midnight = day_rows[day_rows["timestamp"].dt.time == time(0, 0)]
    return at_midnight.iloc[-1] if not at_midnight.empty else day_rows.iloc[-1]


def _as_aware(value: Any) -> datetime:
    moment = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    if moment.tzinfo is None:
        return moment.replace(tzinfo=VN_TZ)
    return moment


def _session_start(value: Any) -> datetime:
    """Date a session by the day it traded in Vietnam, not by the tick read.

    A closed session comes back stamped midnight, but the one that just closed
    is stamped at its last tick — so the same field would carry a date for some
    sessions and a time of day for others. ``effective_at`` answers "which
    session is this", and every other capability answers it with a day, so this
    one does too. It also makes the two rows the provider emits for one session,
    live then consolidated, the same snapshot: the store keys on
    ``effective_at``, so the consolidated numbers replace the partial ones
    instead of sitting beside them where the later tick stamp would win.
    """
    return _as_aware(value).astimezone(VN_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

