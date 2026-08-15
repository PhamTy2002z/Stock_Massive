"""One Redis arbiter over the whole vnstock account allowance.

Before this module there were three pacers and none of them was the quota: a
process-local ``RequestPacer`` in the vnstock adapters, a sleep between symbols
inside the census, and a ``BoundedSemaphore`` in the vnstock client. Three
uncoordinated copies sharing one account allowance add up to more than the
allowance, and vnstock answers an exhausted quota by calling ``sys.exit()`` —
so the failure mode of getting this wrong is the collector taking the process
with it, an hour into a run nobody is watching.

So the allowance lives in one place, keyed in Redis, and every live vnstock
path passes through it (``docs/adr/0014``, which amends ``docs/adr/0001``):

- **The account bucket** spaces every call by at least 3 seconds without
  ``VNSTOCK_API_KEY`` and 1 second with it — the 20 / 60 rpm allowance vnstock's
  own quota layer grants.
- **The Collector lease** gives the Collector exclusive live-provider access
  while it runs. Every other lane is refused for its duration.
- **News** has its own lower lane at 5 / 15 rpm and still passes through the
  account bucket, because it is spending the same account's allowance.
- **Backfill and the frozen legacy live routes rank below news**: they stand
  aside while a news caller is waiting, and they consume the same account
  bucket when they go.
- **Redis failure is fail-closed.** A Provider Source call with no arbiter is a
  call with no allowance, and the process-local pacer it would fall back on is
  exactly the thing that was measured not to hold. Store-backed APIs are
  untouched by this and keep serving.

The lane is carried in a ``ContextVar`` rather than threaded through thirty
call sites: the entry points that know which lane they are — the Collector, the
census, Backfill, the news reader — set it once, and everything else is legacy
by default, which is the safe answer for a caller that never declared itself.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from secrets import token_hex
from typing import Any

logger = logging.getLogger(__name__)

# The environment variable vnstock's own quota layer reads to decide the tier.
# Read from the environment rather than from settings for the reason the
# adapters already documented: settings also load from a ``.env`` file that
# vnstock never sees, so a key declared only there would triple the pace this
# arbiter keeps while the account stayed on the guest tier.
API_KEY_ENV_VAR = "VNSTOCK_API_KEY"

# The account allowance, as spacing between calls. 20 rpm guest, 60 rpm keyed.
ACCOUNT_SPACING_WITHOUT_KEY = 3.0
ACCOUNT_SPACING_WITH_KEY = 1.0

# The news lane's own lower allowance: 5 rpm guest, 15 rpm keyed. Lower than the
# account on purpose — news is the one cache-aside exception to the rule that
# only the Collector calls a Provider Source, and an exception that may spend
# the whole allowance is not an exception, it is a second collector.
NEWS_SPACING_WITHOUT_KEY = 12.0
NEWS_SPACING_WITH_KEY = 4.0

# How long a reserved slot stays in Redis after it has passed. Long enough that
# a bucket cannot forget a reservation still being waited on, short enough that
# an idle deployment does not keep a stale slot for the next run to trip over.
SLOT_TTL_SECONDS = 300

# The Collector lease. The TTL bounds how long a dead process can lock out
# every other lane; the heartbeat is what keeps a live run holding it.
LEASE_TTL_SECONDS = 300
LEASE_HEARTBEAT_SECONDS = 60

KEY_PREFIX = "stock_massive:vnstock"
ACCOUNT_KEY = f"{KEY_PREFIX}:account"
NEWS_KEY = f"{KEY_PREFIX}:news"
NEWS_WAITING_KEY = f"{KEY_PREFIX}:news:waiting"
COLLECTOR_LEASE_KEY = f"{KEY_PREFIX}:collector:lease"

# How long a waiting-news marker survives a process that died while waiting.
NEWS_WAITING_TTL_SECONDS = 60

# Reserve the next slot in a leaky bucket and say how long the caller must wait
# for it. The value at ``key`` is the millisecond timestamp of the next free
# slot; a caller takes that slot and pushes the marker one spacing further on,
# so concurrent callers queue instead of colliding.
#
# ``tests/fake_redis.py`` mirrors this in Python. A change here that is not made
# there leaves the suite green over a bucket that no longer spaces anything.
RESERVE_SLOT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local spacing = tonumber(ARGV[2])
local max_wait = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local next_at = tonumber(redis.call('GET', key))
if next_at == nil or next_at < now then
  next_at = now
end
local wait = next_at - now
if max_wait >= 0 and wait > max_wait then
  return -1
end
redis.call('SET', key, next_at + spacing, 'PX', ttl)
return wait
"""

# Release only a lease this process still owns. Deleting unconditionally would
# let a process whose lease had already expired delete its successor's.
RELEASE_LEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

RENEW_LEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class QuotaLane(str, Enum):
    """Which claim on the account allowance a call is making.

    Ranked: the Collector excludes everyone while it holds its lease, news
    outranks what is left, and Backfill and the frozen legacy routes come last.
    """

    COLLECTOR = "collector"
    NEWS = "news"
    BACKFILL = "backfill"
    LEGACY = "legacy"


class QuotaRefused(RuntimeError):
    """A Provider Source call the arbiter will not admit."""


class QuotaUnavailable(QuotaRefused):
    """No arbiter is reachable, so no call may be admitted.

    Fail-closed by design. The alternative is a process-local pace that three
    processes would each keep in full, which is the arrangement this module
    replaced.
    """


class CollectorLeaseHeld(QuotaRefused):
    """The Collector holds exclusive live-provider access right now."""


class QuotaWaitTooLong(QuotaRefused):
    """The next free slot is further out than this caller can wait for."""


_active_lane: ContextVar[QuotaLane] = ContextVar(
    "vnstock_quota_lane", default=QuotaLane.LEGACY
)


def active_lane() -> QuotaLane:
    """The lane the current call belongs to, legacy unless declared."""
    return _active_lane.get()


@contextmanager
def quota_lane(lane: QuotaLane) -> Iterator[QuotaLane]:
    """Declare the lane for everything this block calls.

    Set at the entry points that know the answer — ``run_cycle``, the census,
    Backfill, the news reader — so the thirty call sites in between neither
    know nor need to.
    """
    token = _active_lane.set(lane)
    try:
        yield lane
    finally:
        _active_lane.reset(token)


def account_spacing(api_key: str) -> float:
    """The spacing these credentials actually buy."""
    return ACCOUNT_SPACING_WITH_KEY if api_key else ACCOUNT_SPACING_WITHOUT_KEY


def news_spacing(api_key: str) -> float:
    """The news lane's own spacing, always below the account's."""
    return NEWS_SPACING_WITH_KEY if api_key else NEWS_SPACING_WITHOUT_KEY


class VnstockQuotaArbiter:
    """The one thing that decides whether a live vnstock call may happen now."""

    def __init__(
        self,
        redis_factory: Callable[[], Any] | None = None,
        api_key: str | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        yield_step: float = 0.25,
    ) -> None:
        if redis_factory is None:
            from src.core.redis import get_redis

            redis_factory = get_redis
        self._redis_factory = redis_factory
        self._api_key = (
            api_key if api_key is not None else os.environ.get(API_KEY_ENV_VAR, "")
        )
        self._clock = clock
        self._sleep = sleep
        self._yield_step = yield_step
        self.account_spacing = account_spacing(self._api_key)
        self.news_spacing = news_spacing(self._api_key)

    # -- admission --------------------------------------------------------

    def acquire(
        self,
        lane: QuotaLane | None = None,
        max_wait: float | None = None,
    ) -> float:
        """Wait for this call's slot, and return how long that took.

        Raises rather than returns on refusal, because every refusal here means
        the call must not happen: the Collector owns the provider, the wait is
        longer than the caller can spend, or there is no arbiter at all.
        """
        lane = lane or active_lane()
        redis = self._client()

        if lane is not QuotaLane.COLLECTOR and self._lease_held(redis):
            raise CollectorLeaseHeld(
                "the Collector holds exclusive vnstock access while it runs"
            )

        if lane is QuotaLane.NEWS:
            return self._acquire_news(redis, max_wait)

        if lane in (QuotaLane.BACKFILL, QuotaLane.LEGACY):
            self._stand_aside_for_news(redis)

        return self._wait_for_slot(redis, ACCOUNT_KEY, self.account_spacing, max_wait)

    def _acquire_news(self, redis: Any, max_wait: float | None) -> float:
        """Take a news slot and then an account slot.

        Both, because the news lane is a *lower* allowance inside the account's,
        not a second allowance beside it. The waiting marker goes up first so
        Backfill and the legacy routes can see that someone with a user behind
        them is in the queue.
        """
        self._mark_news_waiting(redis, +1)
        try:
            waited = self._wait_for_slot(redis, NEWS_KEY, self.news_spacing, max_wait)
            # A news slot already spent when the account refuses is a slot lost,
            # which errs towards calling less than the lane allows — the right
            # direction for the one exception to the collection boundary.
            remaining = None if max_wait is None else max(0.0, max_wait - waited)
            return waited + self._wait_for_slot(
                redis, ACCOUNT_KEY, self.account_spacing, remaining
            )
        finally:
            self._mark_news_waiting(redis, -1)

    def _wait_for_slot(
        self,
        redis: Any,
        key: str,
        spacing: float,
        max_wait: float | None,
    ) -> float:
        wait_ms = self._reserve(redis, key, spacing, max_wait)
        if wait_ms < 0:
            # Only reachable with a max_wait, because without one every slot is
            # waitable; the reservation was refused rather than taken, so
            # nothing has to be handed back.
            raise QuotaWaitTooLong(
                f"the next {key.rsplit(':', 1)[-1]} slot is further out than "
                f"{max_wait:.1f}s"
            )
        if wait_ms > 0:
            self._sleep(wait_ms / 1000)
        return wait_ms / 1000

    def _reserve(
        self,
        redis: Any,
        key: str,
        spacing: float,
        max_wait: float | None,
    ) -> float:
        now_ms = self._clock() * 1000
        args = [
            now_ms,
            spacing * 1000,
            -1 if max_wait is None else max_wait * 1000,
            SLOT_TTL_SECONDS * 1000,
        ]
        return float(self._eval(redis, RESERVE_SLOT_SCRIPT, [key], args))

    def _stand_aside_for_news(self, redis: Any) -> None:
        """Let a waiting news caller through before taking an account slot.

        Bounded by one news slot: below news does not mean behind news forever,
        and a Backfill that never ran would be its own outage.
        """
        remaining = self.news_spacing
        while remaining > 0 and self._news_waiting(redis) > 0:
            step = min(self._yield_step, remaining)
            self._sleep(step)
            remaining -= step

    # -- the Collector lease ----------------------------------------------

    @contextmanager
    def collector_lease(
        self,
        ttl_seconds: int = LEASE_TTL_SECONDS,
        heartbeat_seconds: int = LEASE_HEARTBEAT_SECONDS,
    ) -> Iterator[str]:
        """Hold exclusive live-provider access for the duration of a block.

        Released three ways, because a run ends three ways: normally, by
        exception — both through the ``finally`` — and by the process dying,
        which the TTL covers. A lease that only released on the happy path would
        lock every other lane out until someone noticed.
        """
        redis = self._client()
        token = token_hex(16)

        try:
            acquired = redis.set(COLLECTOR_LEASE_KEY, token, nx=True, ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001 - any Redis failure is fail-closed
            raise QuotaUnavailable(f"the vnstock arbiter is unreachable: {exc}") from exc

        if not acquired:
            raise CollectorLeaseHeld(
                "another Collector run already holds exclusive vnstock access"
            )

        stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._renew_lease,
            args=(redis, token, stop, ttl_seconds, heartbeat_seconds),
            name="vnstock-collector-lease",
            daemon=True,
        )
        heartbeat.start()

        try:
            yield token
        finally:
            stop.set()
            heartbeat.join(timeout=heartbeat_seconds)
            try:
                self._eval(redis, RELEASE_LEASE_SCRIPT, [COLLECTOR_LEASE_KEY], [token])
            except QuotaUnavailable:
                # The lease expires on its own; losing the release is a delay,
                # not a deadlock, and raising here would replace whatever real
                # failure ended the run.
                logger.warning("Could not release the Collector lease; it will expire")

    def _renew_lease(
        self,
        redis: Any,
        token: str,
        stop: threading.Event,
        ttl_seconds: int,
        heartbeat_seconds: int,
    ) -> None:
        while not stop.wait(heartbeat_seconds):
            try:
                renewed = self._eval(
                    redis, RENEW_LEASE_SCRIPT, [COLLECTOR_LEASE_KEY], [token, ttl_seconds]
                )
            except QuotaUnavailable as exc:
                logger.warning("Could not renew the Collector lease: %s", exc)
                continue
            if not renewed:
                # Someone else owns it now, so renewing would be taking a lease
                # this run no longer has. Loud, because the run is still calling.
                logger.error(
                    "The Collector lease expired while the run was still going; "
                    "other lanes are no longer excluded"
                )
                return

    def collector_lease_held(self) -> bool:
        """Whether any process currently holds exclusive live-provider access."""
        return self._lease_held(self._client())

    def _lease_held(self, redis: Any) -> bool:
        try:
            return redis.get(COLLECTOR_LEASE_KEY) is not None
        except Exception as exc:  # noqa: BLE001 - any Redis failure is fail-closed
            raise QuotaUnavailable(f"the vnstock arbiter is unreachable: {exc}") from exc

    # -- news priority ----------------------------------------------------

    def _news_waiting(self, redis: Any) -> int:
        try:
            waiting = redis.get(NEWS_WAITING_KEY)
        except Exception as exc:  # noqa: BLE001 - any Redis failure is fail-closed
            raise QuotaUnavailable(f"the vnstock arbiter is unreachable: {exc}") from exc
        try:
            return max(0, int(waiting or 0))
        except (TypeError, ValueError):
            return 0

    def _mark_news_waiting(self, redis: Any, delta: int) -> None:
        try:
            if delta > 0:
                redis.incr(NEWS_WAITING_KEY)
                # A process that dies mid-wait would otherwise leave a marker
                # that makes every lower lane stand aside for nobody.
                redis.expire(NEWS_WAITING_KEY, NEWS_WAITING_TTL_SECONDS)
            else:
                redis.decr(NEWS_WAITING_KEY)
        except Exception as exc:  # noqa: BLE001 - any Redis failure is fail-closed
            raise QuotaUnavailable(f"the vnstock arbiter is unreachable: {exc}") from exc

    # -- Redis plumbing ---------------------------------------------------

    def _client(self) -> Any:
        redis = self._redis_factory()
        if redis is None:
            raise QuotaUnavailable(
                "no Redis is configured, so no vnstock allowance can be enforced "
                "and no Provider Source call is admitted"
            )
        return redis

    def _eval(self, redis: Any, script: str, keys: list[str], args: list[Any]) -> Any:
        """Run a script against either client this deployment might be using.

        redis-py takes the key count positionally and Upstash takes keyword
        lists; both are configured shapes, so both are spoken here.
        """
        try:
            try:
                return redis.eval(script, keys=keys, args=args)
            except TypeError:
                return redis.eval(script, len(keys), *keys, *args)
        except QuotaRefused:
            raise
        except Exception as exc:  # noqa: BLE001 - any Redis failure is fail-closed
            raise QuotaUnavailable(f"the vnstock arbiter is unreachable: {exc}") from exc


_arbiter: VnstockQuotaArbiter | None = None
_arbiter_lock = threading.Lock()


def quota_arbiter() -> VnstockQuotaArbiter:
    """The arbiter every live vnstock path shares."""
    global _arbiter
    if _arbiter is None:
        with _arbiter_lock:
            if _arbiter is None:
                _arbiter = VnstockQuotaArbiter()
    return _arbiter


def set_quota_arbiter(arbiter: VnstockQuotaArbiter | None) -> None:
    """Install an arbiter, or clear it after a configuration change or in tests."""
    global _arbiter
    with _arbiter_lock:
        _arbiter = arbiter


__all__ = [
    "ACCOUNT_KEY",
    "ACCOUNT_SPACING_WITHOUT_KEY",
    "ACCOUNT_SPACING_WITH_KEY",
    "COLLECTOR_LEASE_KEY",
    "NEWS_KEY",
    "NEWS_SPACING_WITHOUT_KEY",
    "NEWS_SPACING_WITH_KEY",
    "NEWS_WAITING_KEY",
    "RELEASE_LEASE_SCRIPT",
    "RENEW_LEASE_SCRIPT",
    "RESERVE_SLOT_SCRIPT",
    "CollectorLeaseHeld",
    "QuotaLane",
    "QuotaRefused",
    "QuotaUnavailable",
    "QuotaWaitTooLong",
    "VnstockQuotaArbiter",
    "account_spacing",
    "active_lane",
    "news_spacing",
    "quota_arbiter",
    "quota_lane",
    "set_quota_arbiter",
]
