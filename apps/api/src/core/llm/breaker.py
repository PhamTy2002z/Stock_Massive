"""One Redis arbiter over the LLM route's rate limit, and it fails **open**.

``core/quota.py`` solved this shape once for vnstock, and its opening sentence is
the reason it exists: *"Before this module there were three pacers and none of
them was the quota."* The LLM route has the same arrangement one layer up. The
Collector's nightly lane and an interactive Turn share one route allowance, they
run in separate processes whenever the Eval Battery or a second worktree is up,
and neither can see the 429 the other just received — so both keep asking, and
each answer costs a paid request to be told *not now*.

So a 429 is written once, to Redis, keyed by route and model, and every caller
reads it before dispatch.

**Where this deliberately departs from** ``quota.py``: that module fails
**closed**, and it is right to. Its subject is a paid account allowance whose
exhaustion makes vnstock call ``sys.exit()``, so a call nothing is counting is a
call that must not happen. This breaker's subject is different in both directions.
The route enforces its own limit server-side — the breaker only saves the paid
request that would have been refused anyway — and the cost of getting it wrong is
not an overspend but a blank answer on a screen somebody is watching. A Redis
outage must not be able to stop every Turn, so every failure in here admits the
call and says so in the log. That is the same direction ``ADR-0021`` chose for the
Recommendation Validator, for the same reason.

Two consequences of failing open, stated so neither is a surprise:

- with Redis down the system behaves exactly as it did before this module: each
  caller discovers the rate limit for itself, at the cost of one refused request;
- a hold is capped at :data:`MAX_HOLD_SECONDS` however far away the route says its
  window resets. A per-day limit really does reset eight hours later, but a hold
  that long is indistinguishable from an outage, and a route that has recovered
  early can only be discovered by asking it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from src.core.redis import eval_script, get_redis

logger = logging.getLogger(__name__)

KEY_PREFIX = "stock_massive:llm:breaker"

# What a 429 with no ``Retry-After`` buys. Short on purpose: the header is the
# route's own answer and this is only the guess for when it did not give one.
DEFAULT_HOLD_SECONDS = 20.0

# The ceiling on any hold, whatever the route said. See the module docstring.
MAX_HOLD_SECONDS = 300.0

# Open the breaker to the later of what it already holds and what this caller
# learned, and answer with how long the hold now has left. Written as a script
# because two callers rate-limited in the same second must not shorten each
# other's hold, which a read-then-write from Python does exactly half the time.
#
# ``tests/fake_redis.py`` mirrors this in Python. A change here that is not made
# there raises ``UnknownScript`` rather than passing quietly.
OPEN_BREAKER_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local until_at = tonumber(ARGV[2])
local held = tonumber(redis.call('GET', key))
if held ~= nil and held > until_at then
  until_at = held
end
if until_at <= now then
  redis.call('DEL', key)
  return 0
end
redis.call('SET', key, until_at, 'PX', until_at - now)
return until_at - now
"""


def route_key(base_url: str, model: str) -> str:
    """One key per route host and model.

    The host rather than the whole URL: a base URL differing only by path is the
    same allowance, and the credential can appear in a query string, which is not
    a thing to write into a Redis key.
    """
    host = urlsplit(base_url).netloc or base_url.strip().strip("/")
    return f"{KEY_PREFIX}:{host}:{model}"


class RouteBreaker:
    """Whether this route is known to be rate-limited right now.

    Every method answers rather than raises. The only failure this class can
    have is *not knowing*, and not knowing admits the call.
    """

    def __init__(
        self,
        redis_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = time.time,
        enabled: bool = True,
    ) -> None:
        self._redis_factory = redis_factory or get_redis
        self._clock = clock
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """The kill switch, read per call so a flip needs no restart."""
        return self._enabled

    def open_for(self, key: str) -> float:
        """Seconds the hold has left, or ``0.0`` when the route may be called.

        Zero is also what a broken Redis, an absent Redis and a disabled breaker
        answer: the caller may not tell them apart, and must not have to.
        """
        if not self._enabled:
            return 0.0
        try:
            redis = self._redis_factory()
            if redis is None:
                return 0.0
            held = redis.get(key)
            if held is None:
                return 0.0
            remaining = float(held) / 1000 - self._clock()
        except Exception as exc:  # noqa: BLE001 - fail open, whatever broke
            logger.debug("The LLM route breaker could not be read: %s", exc)
            return 0.0
        if remaining <= 0:
            return 0.0
        return min(remaining, MAX_HOLD_SECONDS)

    def record_rate_limit(
        self,
        key: str,
        retry_after: float | None = None,
        reset_at: float | None = None,
    ) -> float:
        """Open the breaker from what the route's own headers said.

        ``Retry-After`` is preferred over ``X-RateLimit-Reset`` because it is
        relative: a reset epoch from a route whose clock disagrees with ours by a
        minute is a hold that is a minute wrong in a direction nobody can see.
        """
        if not self._enabled:
            return 0.0
        hold = _hold_seconds(retry_after, reset_at, self._clock())
        try:
            redis = self._redis_factory()
            if redis is None:
                return 0.0
            now_ms = self._clock() * 1000
            remaining_ms = float(
                eval_script(
                    redis,
                    OPEN_BREAKER_SCRIPT,
                    [key],
                    [now_ms, now_ms + hold * 1000],
                )
            )
        except Exception as exc:  # noqa: BLE001 - fail open, whatever broke
            logger.debug("The LLM route breaker could not be opened: %s", exc)
            return 0.0
        logger.info(
            "The LLM route is rate-limited; holding %s for %.1fs",
            key,
            remaining_ms / 1000,
        )
        return remaining_ms / 1000

    def clear(self, key: str) -> None:
        """Close the breaker by hand, for an operator and for tests."""
        try:
            redis = self._redis_factory()
            if redis is not None:
                redis.delete(key)
        except Exception as exc:  # noqa: BLE001 - fail open, whatever broke
            logger.debug("The LLM route breaker could not be cleared: %s", exc)


def _hold_seconds(
    retry_after: float | None,
    reset_at: float | None,
    now: float,
) -> float:
    """How long to hold, from whatever the route was willing to say."""
    candidate: float | None = None
    if retry_after is not None and retry_after > 0:
        candidate = retry_after
    elif reset_at is not None:
        candidate = reset_at - now
    if candidate is None or candidate <= 0:
        candidate = DEFAULT_HOLD_SECONDS
    return min(candidate, MAX_HOLD_SECONDS)


__all__ = [
    "DEFAULT_HOLD_SECONDS",
    "MAX_HOLD_SECONDS",
    "OPEN_BREAKER_SCRIPT",
    "RouteBreaker",
    "route_key",
]
