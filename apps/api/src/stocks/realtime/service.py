"""Source-neutral bounded reads over durable realtime evidence and projections."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from .contracts import EventFamily, MarketDataSource, NormalizedMarketEvent
from .health import HealthSnapshot
from .projections import HotProjectionStore, ProjectionUnavailable
from .storage import Checkpoint, RealtimeEventStore


MAX_EVENT_PAGE_SIZE = 500
EVENT_WINDOW_LIMITS = {
    EventFamily.TRADE: timedelta(days=1),
    EventFamily.FOREIGN_FLOW: timedelta(days=1),
    EventFamily.CLOSED_BAR: timedelta(days=31),
}


class RealtimeEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source: MarketDataSource
    family: EventFamily
    symbol: str
    exchange: str
    board: str
    trading_day: str
    session: str
    provider_time: datetime
    observed_time: datetime
    freshness_seconds: float = Field(ge=0)
    units: dict[str, str]
    quality_state: str
    schema_version: int
    normalization_version: int
    data: dict[str, Any]


class RealtimePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[RealtimeEvidenceResponse, ...]
    next_cursor: str | None


class RealtimeProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    board: str
    projections: dict[str, dict[str, Any]]


class RealtimeProjectionBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board: str
    items: tuple[RealtimeProjectionResponse, ...]
    feed: HealthSnapshot | None
    data: HealthSnapshot | None


class RealtimeReadService:
    """Enforce Universe, window, cursor, and provider-isolation boundaries."""

    def __init__(
        self,
        store: RealtimeEventStore,
        projections: HotProjectionStore,
        universe_symbols: tuple[str, ...],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._projections = projections
        self._universe = frozenset(symbol.upper() for symbol in universe_symbols)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def events(
        self,
        family: EventFamily,
        symbol: str,
        *,
        start: datetime,
        end: datetime,
        source: MarketDataSource | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> RealtimePageResponse:
        normalized = self._require_symbol(symbol)
        _validate_window(family, start, end, limit)
        after = (
            _decode_cursor(cursor, family, normalized, start, end, source)
            if cursor is not None
            else None
        )
        page = await self._store.query(
            family,
            normalized,
            start=start,
            end=end,
            source=source,
            after=after,
            limit=limit,
        )
        now = self._clock()
        return RealtimePageResponse(
            items=tuple(_evidence_response(event, now) for event in page.events),
            next_cursor=(
                _encode_cursor(
                    page.next_cursor,
                    family,
                    normalized,
                    start,
                    end,
                    source,
                )
                if page.next_cursor is not None
                else None
            ),
        )

    async def metrics(self, symbol: str, board: str) -> RealtimeProjectionResponse:
        normalized = self._require_symbol(symbol)
        identity = board.upper()
        if identity not in {"G1", "G4"}:
            raise ValueError("realtime projection board must be G1 or G4")
        values: dict[str, dict[str, Any]] = {}
        for kind in ("trade_metrics", "foreign_flow", "upcom_reference_input"):
            value = await self._projections.read_metric(kind, normalized, identity)
            if value is not None:
                try:
                    as_of = datetime.fromisoformat(str(value["as_of"]))
                except (KeyError, TypeError, ValueError) as exc:
                    raise ProjectionUnavailable(
                        "realtime metric has no valid as-of time"
                    ) from exc
                if as_of.tzinfo is None:
                    raise ProjectionUnavailable(
                        "realtime metric has no valid as-of time"
                    )
                enriched = dict(value)
                enriched["freshness_seconds"] = max(
                    0.0,
                    (self._clock() - as_of).total_seconds(),
                )
                values[kind] = enriched
        return RealtimeProjectionResponse(
            symbol=normalized,
            board=identity,
            projections=values,
        )

    async def metrics_many(
        self,
        symbols: tuple[str, ...],
        board: str = "G1",
    ) -> RealtimeProjectionBatchResponse:
        if not 1 <= len(symbols) <= 100:
            raise ValueError("realtime bulk metrics require between 1 and 100 symbols")
        identity = board.upper()
        if identity not in {"G1", "G4"}:
            raise ValueError("realtime projection board must be G1 or G4")
        names = tuple(sorted({self._require_symbol(symbol) for symbol in symbols}))
        values, feed, data = await asyncio.gather(
            self._projections.read_metrics(names, identity),
            self._store.read_health("feed"),
            self._store.read_health("data"),
        )
        now = self._clock()
        items = tuple(
            RealtimeProjectionResponse(
                symbol=symbol,
                board=identity,
                projections={
                    kind: _with_freshness(value, now)
                    for kind, value in values[(symbol, identity)].items()
                },
            )
            for symbol in names
        )
        return RealtimeProjectionBatchResponse(
            board=identity,
            items=items,
            feed=feed,
            data=data,
        )

    def _require_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        if normalized not in self._universe:
            raise LookupError("symbol is not in the configured Universe")
        return normalized


def _validate_window(
    family: EventFamily,
    start: datetime,
    end: datetime,
    limit: int,
) -> None:
    if family not in EVENT_WINDOW_LIMITS:
        raise ValueError("event family is not exposed by the S3 API")
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("realtime API requires a valid timezone-aware window")
    if end - start > EVENT_WINDOW_LIMITS[family]:
        raise ValueError(
            f"{family.value} window exceeds {EVENT_WINDOW_LIMITS[family]}"
        )
    if not 1 <= limit <= MAX_EVENT_PAGE_SIZE:
        raise ValueError(
            f"realtime page limit must be between 1 and {MAX_EVENT_PAGE_SIZE}"
        )


def _with_freshness(value: dict[str, Any], now: datetime) -> dict[str, Any]:
    try:
        as_of = datetime.fromisoformat(str(value["as_of"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectionUnavailable("realtime metric has no valid as-of time") from exc
    if as_of.tzinfo is None:
        raise ProjectionUnavailable("realtime metric has no valid as-of time")
    enriched = dict(value)
    enriched["freshness_seconds"] = max(0.0, (now - as_of).total_seconds())
    return enriched


def _evidence_response(
    event: NormalizedMarketEvent,
    now: datetime,
) -> RealtimeEvidenceResponse:
    metadata = event.metadata
    age = max(0.0, (now - metadata.observed_time).total_seconds())
    data = event.model_dump(mode="json", exclude={"metadata"})
    return RealtimeEvidenceResponse(
        evidence_id=metadata.evidence_id,
        source=metadata.source,
        family=metadata.event_family,
        symbol=metadata.symbol,
        exchange=metadata.exchange.value,
        board=metadata.board,
        trading_day=metadata.trading_day.isoformat(),
        session=metadata.session.value,
        provider_time=metadata.provider_time,
        observed_time=metadata.observed_time,
        freshness_seconds=age,
        units=metadata.units.model_dump(mode="json"),
        quality_state=metadata.quality_state.value,
        schema_version=metadata.schema_version,
        normalization_version=metadata.normalization_version,
        data=data,
    )


def _encode_cursor(
    checkpoint: Checkpoint,
    family: EventFamily,
    symbol: str,
    start: datetime,
    end: datetime,
    source: MarketDataSource | None,
) -> str:
    payload = {
        "v": 1,
        "family": family.value,
        "symbol": symbol,
        "start": start.astimezone(UTC).isoformat(),
        "end": end.astimezone(UTC).isoformat(),
        "source": source.value if source is not None else None,
        "provider_time": checkpoint.provider_time.astimezone(UTC).isoformat(),
        "observed_time": checkpoint.observed_time.astimezone(UTC).isoformat(),
        "evidence_id": checkpoint.evidence_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(
    cursor: str,
    family: EventFamily,
    symbol: str,
    start: datetime,
    end: datetime,
    source: MarketDataSource | None,
) -> Checkpoint:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        expected = {
            "v": 1,
            "family": family.value,
            "symbol": symbol,
            "start": start.astimezone(UTC).isoformat(),
            "end": end.astimezone(UTC).isoformat(),
            "source": source.value if source is not None else None,
        }
        if not isinstance(payload, dict) or any(
            payload.get(key) != value for key, value in expected.items()
        ):
            raise ValueError
        provider_time = datetime.fromisoformat(payload["provider_time"])
        observed_time = datetime.fromisoformat(payload["observed_time"])
        if provider_time.tzinfo is None or observed_time.tzinfo is None:
            raise ValueError
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        if not start_utc <= provider_time.astimezone(UTC) < end_utc:
            raise ValueError
        if observed_time < provider_time:
            raise ValueError
        evidence_id = str(payload["evidence_id"])
        if (
            len(evidence_id) != 68
            or not evidence_id.startswith("evt_")
            or any(
                character not in "0123456789abcdef"
                for character in evidence_id[4:]
            )
        ):
            raise ValueError
        return Checkpoint(
            consumer="realtime-api",
            partition_key=f"{family.value}:{symbol}",
            evidence_id=evidence_id,
            provider_time=provider_time,
            observed_time=observed_time,
        )
    except (binascii.Error, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid realtime cursor") from exc
