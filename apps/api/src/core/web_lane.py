"""Redis-bounded cache-aside lane for open-web search and page reads."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from secrets import token_hex
from typing import Any, Literal

from src.core.redis import RELEASE_IF_OWNED_SCRIPT, eval_script

logger = logging.getLogger(__name__)

KEY_PREFIX = "stock_massive:web"
SEARCH_FRESH_SECONDS = 30 * 60
SEARCH_STALE_SECONDS = 24 * 60 * 60
URL_FRESH_SECONDS = 24 * 60 * 60
URL_STALE_SECONDS = 7 * 24 * 60 * 60
SINGLE_FLIGHT_TTL_SECONDS = 30
REQUESTS_PER_MINUTE = 30

WebKind = Literal["search", "url"]


class WebUnavailable(RuntimeError):
    """Neither a fresh upstream response nor a bounded stale value is available."""


@dataclass(frozen=True)
class WebRead:
    """One cached or freshly fetched web response with explicit freshness."""

    payload: Any
    fetched_at: float
    age_seconds: float
    stale: bool


class WebLane:
    """Cache, single-flight, and rate-limit one independent provider lane."""

    def __init__(
        self,
        redis_factory: Callable[[], Any] | None = None,
        *,
        clock: Callable[[], float] = time.time,
        requests_per_minute: int = REQUESTS_PER_MINUTE,
    ) -> None:
        if redis_factory is None:
            from src.core.redis import get_redis

            redis_factory = get_redis
        self._redis_factory = redis_factory
        self._clock = clock
        self._requests_per_minute = requests_per_minute

    def read(self, kind: WebKind, key: str, fetch: Callable[[], Any]) -> WebRead:
        """Read through the cache, serving labelled stale data on upstream failure."""
        redis = self._client()
        digest = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()
        stored = self._stored(redis, kind, digest)
        fresh_seconds, stale_seconds = self._windows(kind)
        if stored is not None and stored.age_seconds <= fresh_seconds:
            return stored

        token = self._claim(redis, kind, digest)
        if token is None:
            return self._fallback(stored, stale_seconds, "another request is refreshing")
        try:
            self._take_allowance(redis)
            payload = fetch()
        except Exception as exc:  # noqa: BLE001 - stale service is the contract
            logger.warning("Open-web %s read failed: %s", kind, exc)
            return self._fallback(stored, stale_seconds, str(exc))
        finally:
            self._release(redis, kind, digest, token)
        return self._store(redis, kind, digest, payload, stale_seconds)

    def _stored(self, redis: Any, kind: WebKind, digest: str) -> WebRead | None:
        try:
            raw = redis.get(self._key(kind, digest))
        except Exception as exc:  # noqa: BLE001
            raise WebUnavailable(f"the web cache is unreachable: {exc}") from exc
        if not raw:
            return None
        try:
            record = json.loads(raw)
            fetched_at = float(record["fetched_at"])
            payload = record["payload"]
        except (TypeError, ValueError, KeyError):
            logger.warning("Discarding an unreadable cached web record")
            return None
        age = max(0.0, self._clock() - fetched_at)
        return WebRead(payload, fetched_at, age, age > self._windows(kind)[0])

    def _store(
        self,
        redis: Any,
        kind: WebKind,
        digest: str,
        payload: Any,
        stale_seconds: int,
    ) -> WebRead:
        now = self._clock()
        record = json.dumps({"fetched_at": now, "payload": payload})
        try:
            redis.set(self._key(kind, digest), record, ex=stale_seconds)
        except Exception as exc:  # noqa: BLE001
            raise WebUnavailable(f"the web response could not be cached: {exc}") from exc
        return WebRead(payload, now, 0.0, False)

    @staticmethod
    def _fallback(stored: WebRead | None, stale_seconds: int, reason: str) -> WebRead:
        if stored is not None and stored.age_seconds <= stale_seconds:
            logger.info("Serving stale open-web data: %s", reason)
            return WebRead(stored.payload, stored.fetched_at, stored.age_seconds, True)
        raise WebUnavailable(f"no open-web data is available: {reason}")

    def _take_allowance(self, redis: Any) -> None:
        minute = int(self._clock() // 60)
        key = f"{KEY_PREFIX}:allowance:{minute}"
        try:
            count = int(redis.incr(key))
            if count == 1:
                redis.expire(key, 61)
        except Exception as exc:  # noqa: BLE001
            raise WebUnavailable(f"the web allowance is unreachable: {exc}") from exc
        if count > self._requests_per_minute:
            raise WebUnavailable("the independent web request allowance is exhausted")

    def _claim(self, redis: Any, kind: WebKind, digest: str) -> str | None:
        token = token_hex(8)
        try:
            claimed = redis.set(
                self._lock_key(kind, digest),
                token,
                nx=True,
                ex=SINGLE_FLIGHT_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise WebUnavailable(f"the web cache is unreachable: {exc}") from exc
        return token if claimed else None

    def _release(self, redis: Any, kind: WebKind, digest: str, token: str) -> None:
        try:
            eval_script(redis, RELEASE_IF_OWNED_SCRIPT, [self._lock_key(kind, digest)], [token])
        except Exception as exc:  # noqa: BLE001 - the lock has its own TTL
            logger.warning("Could not release the web refresh lock: %s", exc)

    def _client(self) -> Any:
        redis = self._redis_factory()
        if redis is None:
            raise WebUnavailable("no Redis is configured, so the web lane is disabled")
        return redis

    @staticmethod
    def _windows(kind: WebKind) -> tuple[int, int]:
        return (
            (SEARCH_FRESH_SECONDS, SEARCH_STALE_SECONDS)
            if kind == "search"
            else (URL_FRESH_SECONDS, URL_STALE_SECONDS)
        )

    @staticmethod
    def _key(kind: WebKind, digest: str) -> str:
        return f"{KEY_PREFIX}:{kind}:{digest}"

    @staticmethod
    def _lock_key(kind: WebKind, digest: str) -> str:
        return f"{KEY_PREFIX}:{kind}:{digest}:refreshing"


__all__ = [
    "SEARCH_FRESH_SECONDS",
    "URL_FRESH_SECONDS",
    "WebLane",
    "WebRead",
    "WebUnavailable",
]
