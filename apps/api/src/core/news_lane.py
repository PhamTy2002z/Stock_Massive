"""The one cache-aside exception to the collection boundary, made bounded.

ADR-0001 says the Collector is the only caller of a Provider Source, and
``docs/adr/0014`` names exactly one exception: ``search_news``. The value of a
news item falls by the hour, so a six-hour-old Snapshot of it is not the same
answer — which is why news, alone, may leave the rule.

What keeps that an exception rather than a precedent is this module. A news read
is not a free live call; it is:

- a **6-hour fresh cache**, so the common case reaches nobody,
- **per-symbol single-flight**, so ten readers asking about one symbol at once
  make one upstream call between them,
- the **5 / 15 rpm news lane** of the account arbiter, taken through the same
  bucket every other live path takes, and
- **visibly stale service for at most 24 hours** when the Collector holds its
  lease or the provider is failing — stale and labelled, never silently old and
  never a call that walks around the allowance.

The consumer arrives with the Tool Catalog in A5. The lane is here because it is
an allowance rule, and allowance rules written per caller are what
``src/core/quota.py`` exists to stop.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from secrets import token_hex
from typing import Any

from src.core.quota import QuotaLane, QuotaRefused, quota_lane
from src.core.redis import RELEASE_IF_OWNED_SCRIPT, eval_script

logger = logging.getLogger(__name__)

KEY_PREFIX = "stock_massive:news"

# How long a stored read counts as current. Six hours is the figure ADR-0014
# names; it is also roughly the gap between a session close and the evening's
# reporting, so a reader in the morning does not see yesterday's afternoon.
FRESH_SECONDS = 6 * 60 * 60

# How long a stored read may still be served once it has gone off. Past this it
# is not old news, it is no news: a day-old headline offered as today's is worse
# than saying there is nothing to show.
STALE_LIMIT_SECONDS = 24 * 60 * 60

# How long one reader may hold the right to refresh a symbol. Long enough to
# cover a news slot's wait plus the call, short enough that a reader that died
# holding it does not freeze the symbol for the rest of the day.
SINGLE_FLIGHT_TTL_SECONDS = 60


class NewsUnavailable(RuntimeError):
    """No news can be served for this symbol right now.

    Distinct from an empty result: a symbol with no recent news has an answer,
    and this is the absence of one.
    """


@dataclass(frozen=True)
class NewsRead:
    """What was served, and how old it is — the age is part of the answer.

    ``stale`` is carried rather than derived by the caller so that no interface
    can render a day-old read as current by forgetting to compare timestamps.
    """

    symbol: str
    payload: Any
    fetched_at: float
    age_seconds: float
    stale: bool


class NewsLane:
    """Cache-aside reads for one symbol's news, inside the account allowance."""

    def __init__(
        self,
        redis_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = time.time,
        fresh_seconds: int = FRESH_SECONDS,
        stale_limit_seconds: int = STALE_LIMIT_SECONDS,
        single_flight_ttl: int = SINGLE_FLIGHT_TTL_SECONDS,
    ) -> None:
        if redis_factory is None:
            from src.core.redis import get_redis

            redis_factory = get_redis
        self._redis_factory = redis_factory
        self._clock = clock
        self._fresh_seconds = fresh_seconds
        self._stale_limit_seconds = stale_limit_seconds
        self._single_flight_ttl = single_flight_ttl

    def read(self, symbol: str, fetch: Callable[[], Any]) -> NewsRead:
        """Serve this symbol's news, refreshing it only if that is allowed now.

        ``fetch`` performs the live read and returns something JSON-serialisable.
        It is called inside the news lane, so it passes through the same account
        bucket as everything else and is refused outright while the Collector
        holds its lease.
        """
        symbol = symbol.strip().upper()
        redis = self._client()
        stored = self._stored(redis, symbol)

        if stored is not None and stored.age_seconds <= self._fresh_seconds:
            return stored

        token = self._claim_refresh(redis, symbol)
        if token is None:
            # Another reader is already fetching this symbol. Waiting behind it
            # would spend the caller's time to arrive at the answer that is
            # already on the table.
            return self._fall_back(symbol, stored, "another reader is refreshing it")

        try:
            with quota_lane(QuotaLane.NEWS):
                payload = fetch()
        except QuotaRefused as exc:
            return self._fall_back(symbol, stored, str(exc))
        except Exception as exc:  # noqa: BLE001 - any provider failure serves stale
            logger.warning("Live news read failed for %s: %s", symbol, exc)
            return self._fall_back(symbol, stored, str(exc))
        finally:
            self._release_refresh(redis, symbol, token)

        return self._store(redis, symbol, payload)

    # -- what is on the table ---------------------------------------------

    def _stored(self, redis: Any, symbol: str) -> NewsRead | None:
        try:
            raw = redis.get(self._key(symbol))
        except Exception as exc:  # noqa: BLE001 - fail closed like the arbiter
            raise NewsUnavailable(f"the news cache is unreachable: {exc}") from exc
        if not raw:
            return None

        try:
            record = json.loads(raw)
            fetched_at = float(record["fetched_at"])
            payload = record["payload"]
        except (TypeError, ValueError, KeyError):
            logger.warning("Discarding an unreadable cached news record for %s", symbol)
            return None

        age = max(0.0, self._clock() - fetched_at)
        return NewsRead(
            symbol=symbol,
            payload=payload,
            fetched_at=fetched_at,
            age_seconds=age,
            stale=age > self._fresh_seconds,
        )

    def _store(self, redis: Any, symbol: str, payload: Any) -> NewsRead:
        now = self._clock()
        record = json.dumps({"fetched_at": now, "payload": payload})
        try:
            # The key expires at the stale limit rather than at the fresh
            # window: between the two it is still servable, and a cache that
            # dropped it at six hours would leave nothing to fall back on for
            # exactly the outage this lane is written for.
            redis.set(self._key(symbol), record, ex=self._stale_limit_seconds)
        except Exception as exc:  # noqa: BLE001 - Redis is the admission boundary
            raise NewsUnavailable(
                f"the fresh news read could not be admitted to the cache: {exc}"
            ) from exc
        return NewsRead(
            symbol=symbol,
            payload=payload,
            fetched_at=now,
            age_seconds=0.0,
            stale=False,
        )

    def _fall_back(
        self,
        symbol: str,
        stored: NewsRead | None,
        reason: str,
    ) -> NewsRead:
        if stored is not None and stored.age_seconds <= self._stale_limit_seconds:
            logger.info(
                "Serving %s news %.0f minutes old: %s",
                symbol,
                stored.age_seconds / 60,
                reason,
            )
            return stored
        raise NewsUnavailable(f"no news is available for {symbol}: {reason}")

    # -- single flight ----------------------------------------------------

    def _claim_refresh(self, redis: Any, symbol: str) -> str | None:
        token = token_hex(8)
        try:
            claimed = redis.set(
                self._lock_key(symbol), token, nx=True, ex=self._single_flight_ttl
            )
        except Exception as exc:  # noqa: BLE001 - fail closed like the arbiter
            raise NewsUnavailable(f"the news cache is unreachable: {exc}") from exc
        return token if claimed else None

    def _release_refresh(self, redis: Any, symbol: str, token: str) -> None:
        """Give the claim back, and only if it is still this reader's.

        One compare-and-delete rather than a read then a delete: between those
        two round-trips the claim can expire and be taken, and the reader that
        lost it would then release its successor's.
        """
        try:
            eval_script(
                redis, RELEASE_IF_OWNED_SCRIPT, [self._lock_key(symbol)], [token]
            )
        except Exception as exc:  # noqa: BLE001 - the TTL releases it either way
            logger.warning("Could not release the news refresh lock: %s", exc)

    # -- plumbing ---------------------------------------------------------

    def _client(self) -> Any:
        redis = self._redis_factory()
        if redis is None:
            # Fail closed, for the arbiter's reason: with no Redis there is no
            # cache, no single flight and no lane — the live call this would
            # otherwise make is exactly the unbounded one the exception was
            # granted on condition of not being.
            raise NewsUnavailable(
                "no Redis is configured, so the news lane cannot be bounded"
            )
        return redis

    def _key(self, symbol: str) -> str:
        return f"{KEY_PREFIX}:{symbol}"

    def _lock_key(self, symbol: str) -> str:
        return f"{KEY_PREFIX}:{symbol}:refreshing"


__all__ = [
    "FRESH_SECONDS",
    "SINGLE_FLIGHT_TTL_SECONDS",
    "STALE_LIMIT_SECONDS",
    "NewsLane",
    "NewsRead",
    "NewsUnavailable",
]
