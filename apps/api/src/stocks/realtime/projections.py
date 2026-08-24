"""Redis hot projections rebuilt from normalized durable realtime events."""

from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from src.core.redis import eval_script, get_redis

from .contracts import EventFamily, NormalizedMarketEvent
from .health import HealthSnapshot
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
        family: EventFamily, symbol: str, *, board: str | None = None
    ) -> str:
        if family is EventFamily.SESSION:
            identity = (board or symbol).upper()
            return f"stock:realtime:projection:session:{identity}"
        return f"stock:realtime:projection:{family.value}:{symbol.upper()}"

    async def apply(self, event: NormalizedMarketEvent) -> bool:
        redis = self._client()
        metadata = event.metadata
        data_key = self.key(
            metadata.event_family,
            metadata.symbol,
            board=metadata.board,
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
    ) -> dict[str, Any] | None:
        try:
            raw = self._client().get(self.key(family, symbol, board=board))
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
            raise ProjectionUnavailable("Redis is not configured for realtime projections")
        return self._redis
