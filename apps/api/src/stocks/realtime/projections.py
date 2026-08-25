"""Redis hot projections rebuilt from normalized durable realtime events."""

from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from src.core.redis import eval_script, get_redis

from .contracts import ClosedBar, EventFamily, NormalizedMarketEvent
from .health import HealthSnapshot
from .metrics import (
    ForeignFlowProjection,
    ProjectionIdentity,
    TradeMetricsProjection,
    UpcomReferenceInput,
)
from .policy import RetentionClass, retention_rule
from .storage import serialize_event


_UPDATE_IF_NEWER = """
local current = redis.call('GET', KEYS[1])
if current and current >= ARGV[1] then
    return 0
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
return 1
"""


class ProjectionUnavailable(RuntimeError):
    pass


class HotProjectionStore:
    """Idempotent last-event views; PostgreSQL remains the durable owner."""

    def __init__(self, redis: Any | None = None) -> None:
        self._redis = get_redis() if redis is None else redis
        self._ttl = retention_rule(RetentionClass.PROJECTION).days * 24 * 60 * 60

    @staticmethod
    def key(
        family: EventFamily,
        symbol: str,
        *,
        board: str | None = None,
        resolution: str | None = None,
    ) -> str:
        if family is EventFamily.SESSION:
            identity = (board or symbol).upper()
            return f"stock:realtime:projection:session:{identity}"
        identity = [symbol.upper()]
        if board is not None:
            identity.append(board.upper())
        if resolution is not None:
            identity.append(resolution)
        return f"stock:realtime:projection:{family.value}:{':'.join(identity)}"

    @staticmethod
    def metric_key(kind: str, symbol: str, board: str) -> str:
        return f"stock:realtime:metric:{kind}:{symbol.upper()}:{board.upper()}"

    async def apply(self, event: NormalizedMarketEvent) -> bool:
        redis = self._client()
        metadata = event.metadata
        data_key = self.key(
            metadata.event_family,
            metadata.symbol,
            board=metadata.board,
            resolution=(
                event.resolution.value if isinstance(event, ClosedBar) else None
            ),
        )
        order_key = f"{data_key}:order"
        order = "|".join(
            (
                metadata.provider_time.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%fZ"),
                metadata.observed_time.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%fZ"),
                metadata.evidence_id,
            )
        )
        payload = json.dumps(
            {
                "evidence_id": metadata.evidence_id,
                "provider_time": metadata.provider_time.isoformat(),
                "observed_time": metadata.observed_time.isoformat(),
                "event": serialize_event(event),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            result = eval_script(
                redis,
                _UPDATE_IF_NEWER,
                [order_key, data_key],
                [order, payload, self._ttl],
            )
        except Exception as exc:
            raise ProjectionUnavailable("realtime projection write failed") from exc
        return bool(result)

    async def read(
        self,
        family: EventFamily,
        symbol: str,
        *,
        board: str | None = None,
        resolution: str | None = None,
    ) -> dict[str, Any] | None:
        try:
            raw = self._client().get(
                self.key(
                    family,
                    symbol,
                    board=board,
                    resolution=resolution,
                )
            )
        except Exception as exc:
            raise ProjectionUnavailable("realtime projection read failed") from exc
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ProjectionUnavailable("realtime projection is unreadable") from exc
        if not isinstance(value, dict):
            raise ProjectionUnavailable("realtime projection is not an object")
        return value

    async def save_metric(self, projection: ProjectionIdentity) -> bool:
        kind = _metric_kind(projection)
        data_key = self.metric_key(kind, projection.symbol, projection.board)
        order_key = f"{data_key}:order"
        order = "|".join(
            (
                projection.as_of.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%fZ"),
                projection.evidence_ids[-1],
            )
        )
        try:
            result = eval_script(
                self._client(),
                _UPDATE_IF_NEWER,
                [order_key, data_key],
                [order, projection.model_dump_json(), self._ttl],
            )
        except Exception as exc:
            raise ProjectionUnavailable("realtime metric write failed") from exc
        return bool(result)

    async def read_metric(
        self,
        kind: str,
        symbol: str,
        board: str,
    ) -> dict[str, Any] | None:
        try:
            raw = self._client().get(self.metric_key(kind, symbol, board))
        except Exception as exc:
            raise ProjectionUnavailable("realtime metric read failed") from exc
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ProjectionUnavailable("realtime metric is unreadable") from exc
        if not isinstance(value, dict):
            raise ProjectionUnavailable("realtime metric is not an object")
        return value

    async def read_metrics(
        self,
        symbols: tuple[str, ...],
        board: str,
        *,
        kinds: tuple[str, ...] = ("trade_metrics", "foreign_flow"),
    ) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
        """Read a bounded symbol set in one Redis round trip."""
        if not 1 <= len(symbols) <= 100:
            raise ValueError("realtime bulk metrics require between 1 and 100 symbols")
        identity = board.upper()
        if identity not in {"G1", "G4"}:
            raise ValueError("realtime projection board must be G1 or G4")
        allowed = {"trade_metrics", "foreign_flow", "upcom_reference_input"}
        if not kinds or any(kind not in allowed for kind in kinds):
            raise ValueError("unsupported realtime metric kind")

        names = tuple(sorted({symbol.upper() for symbol in symbols}))
        keys = [
            self.metric_key(kind, symbol, identity)
            for symbol in names
            for kind in kinds
        ]
        client = self._client()
        try:
            try:
                raw_values = client.mget(*keys)
            except TypeError:
                raw_values = client.mget(keys)
        except Exception as exc:
            raise ProjectionUnavailable("realtime bulk metric read failed") from exc
        if not isinstance(raw_values, (list, tuple)) or len(raw_values) != len(keys):
            raise ProjectionUnavailable("realtime bulk metric response is invalid")

        result: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        position = 0
        for symbol in names:
            metrics: dict[str, dict[str, Any]] = {}
            for kind in kinds:
                raw = raw_values[position]
                position += 1
                if raw is None:
                    continue
                try:
                    value = json.loads(raw)
                except (TypeError, ValueError) as exc:
                    raise ProjectionUnavailable(
                        "realtime metric is unreadable"
                    ) from exc
                if not isinstance(value, dict):
                    raise ProjectionUnavailable("realtime metric is not an object")
                metrics[kind] = value
            result[(symbol, identity)] = metrics
        return result

    async def save_health(self, snapshot: HealthSnapshot) -> None:
        try:
            self._client().set(
                f"stock:realtime:health:{snapshot.scope}",
                snapshot.model_dump_json(),
                ex=retention_rule(RetentionClass.OPERATIONAL_METADATA).days * 86400,
            )
        except Exception as exc:
            raise ProjectionUnavailable("realtime health projection write failed") from exc

    def _client(self) -> Any:
        if self._redis is None:
            raise ProjectionUnavailable(
                "Redis is not configured for realtime projections"
            )
        return self._redis


def _metric_kind(projection: ProjectionIdentity) -> str:
    if isinstance(projection, TradeMetricsProjection):
        return "trade_metrics"
    if isinstance(projection, ForeignFlowProjection):
        return "foreign_flow"
    if isinstance(projection, UpcomReferenceInput):
        return "upcom_reference_input"
    raise TypeError(f"unsupported realtime metric: {type(projection).__name__}")
