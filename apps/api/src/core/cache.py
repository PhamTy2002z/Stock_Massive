"""Generic trading-hours-aware cache for stock market data."""
import json
import logging
import time as time_module
from secrets import token_hex
from threading import Event, Thread
from datetime import datetime, time
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from src.core.redis import get_redis

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""
_RENEW_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class CacheRefreshUnavailable(RuntimeError):
    """A recent refresh failed, so duplicate upstream calls are suppressed."""


class TradingHoursCache:
    """Cache with trading-hours-aware TTL using Upstash Redis.

    Args:
        key_prefix: Redis key prefix (e.g., "stock:indices:")
        ttl_trading: TTL in seconds during trading hours
        ttl_off_hours: TTL in seconds outside trading hours
    """

    MARKET_OPEN = time(9, 0)
    MARKET_CLOSE = time(15, 0)

    def __init__(
        self,
        key_prefix: str,
        ttl_trading: int,
        ttl_off_hours: int,
        stale_ttl: int | None = None,
    ):
        self.key_prefix = key_prefix
        self.ttl_trading = ttl_trading
        self.ttl_off_hours = ttl_off_hours
        self.stale_ttl = stale_ttl

    def _is_trading_hours(self) -> bool:
        """Check if current time is within VN market hours."""
        now = datetime.now(VN_TZ)
        if now.weekday() > 4:  # Weekend (Sat=5, Sun=6)
            return False
        return self.MARKET_OPEN <= now.time() <= self.MARKET_CLOSE

    def _get_ttl(self) -> int:
        """Get TTL based on current trading status."""
        return self.ttl_trading if self._is_trading_hours() else self.ttl_off_hours

    def get(self, key: str) -> Optional[Any]:
        """Get cached data from Upstash Redis."""
        redis = get_redis()
        if not redis:
            return None

        try:
            full_key = f"{self.key_prefix}{key}"
            data = redis.get(full_key)
            if data is None:
                return None
            # Upstash returns string, parse JSON
            if isinstance(data, str):
                return json.loads(data)
            return data
        except Exception as e:
            logger.warning(f"Redis GET error for {key}: {e}")
            return None

    def get_stale(self, key: str) -> Optional[Any]:
        """Return the last-known-good value after the fresh key expires."""
        if self.stale_ttl is None:
            return None
        redis = get_redis()
        if not redis:
            return None

        try:
            data = redis.get(f"{self.key_prefix}{key}:stale")
            if data is None:
                return None
            return json.loads(data) if isinstance(data, str) else data
        except Exception as e:
            logger.warning(f"Redis stale GET error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store data in Upstash Redis.

        Args:
            ttl: Overrides the trading-hours TTL. Use it for values that are
                known to be incomplete and should be replaced sooner.
        """
        redis = get_redis()
        if not redis:
            return

        try:
            full_key = f"{self.key_prefix}{key}"
            ttl = ttl if ttl is not None else self._get_ttl()
            payload = json.dumps(value, default=str)
            redis.set(full_key, payload, ex=ttl)
            if self.stale_ttl is not None:
                redis.set(f"{full_key}:stale", payload, ex=self.stale_ttl)
        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}")

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], Any],
        *,
        lock_ttl: int = 30,
        wait_timeout: float = 15.0,
        failure_ttl: int = 15,
        suppress_failure: Callable[[Exception], bool] | None = None,
    ) -> Any:
        """Load once per key and serve last-known-good data on upstream failure.

        A short Redis lock coalesces concurrent cold misses across API workers.
        Followers immediately use stale data when available; on a true cold
        start they wait for the lock owner to populate the fresh key.
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        redis = get_redis()
        if not redis:
            return loader()

        full_key = f"{self.key_prefix}{key}"
        lock_key = f"{full_key}:refresh-lock"
        failure_key = f"{full_key}:refresh-failed"

        try:
            refresh_failed = redis.get(failure_key)
        except Exception:
            refresh_failed = None
        if refresh_failed is not None:
            stale = self.get_stale(key)
            if stale is not None:
                return stale
            raise CacheRefreshUnavailable("Data refresh temporarily unavailable")

        lock_token = token_hex(16)
        try:
            owns_lock = bool(redis.set(lock_key, lock_token, nx=True, ex=lock_ttl))
        except Exception as e:
            logger.warning(f"Redis lock SET error for {key}: {e}")
            owns_lock = True

        if not owns_lock:
            stale = self.get_stale(key)
            if stale is not None:
                return stale

            deadline = time_module.monotonic() + wait_timeout
            while time_module.monotonic() < deadline:
                time_module.sleep(0.05)
                cached = self.get(key)
                if cached is not None:
                    return cached
                try:
                    if redis.get(lock_key) is None:
                        break
                except Exception:
                    break

            cached = self.get(key)
            if cached is not None:
                return cached
            stale = self.get_stale(key)
            if stale is not None:
                return stale

            try:
                if redis.get(failure_key) is not None:
                    raise CacheRefreshUnavailable(
                        "Data refresh temporarily unavailable"
                    )
            except CacheRefreshUnavailable:
                raise
            except Exception:
                pass

            try:
                if redis.get(lock_key) is not None:
                    raise CacheRefreshUnavailable("Data refresh in progress")
            except CacheRefreshUnavailable:
                raise
            except Exception:
                # Redis is unavailable, so distributed coordination cannot be
                # trusted; retain the existing fail-open behavior.
                pass
            else:
                # The previous owner disappeared without publishing. Re-enter
                # acquisition rather than running a loader without a lease.
                return self.get_or_load(
                    key,
                    loader,
                    lock_ttl=lock_ttl,
                    wait_timeout=wait_timeout,
                    failure_ttl=failure_ttl,
                    suppress_failure=suppress_failure,
                )

        renewal_stop = Event()
        renewal_thread = None
        if owns_lock:
            renewal_thread = Thread(
                target=self._renew_lock,
                args=(redis, lock_key, lock_token, lock_ttl, renewal_stop),
                daemon=True,
            )
            renewal_thread.start()

        try:
            value = loader()
            self.set(key, value)
            return value
        except Exception as exc:
            if suppress_failure is not None and suppress_failure(exc):
                try:
                    redis.set(failure_key, "1", ex=failure_ttl)
                except Exception:
                    pass
            stale = self.get_stale(key)
            if stale is not None:
                logger.warning("Serving stale cache value for %s", key)
                return stale
            raise
        finally:
            if owns_lock:
                renewal_stop.set()
                if renewal_thread is not None:
                    renewal_thread.join(timeout=1)
                try:
                    self._eval_compare_script(
                        redis,
                        _RELEASE_LOCK_SCRIPT,
                        [lock_key],
                        [lock_token],
                    )
                except Exception as e:
                    logger.warning(f"Redis lock release error for {key}: {e}")

    @staticmethod
    def _eval_compare_script(redis, script: str, keys: list[str], args: list[str]):
        """Execute a small compare-and-mutate script on either Redis client."""
        try:
            return redis.eval(script, keys=keys, args=args)
        except TypeError:
            return redis.eval(script, len(keys), *keys, *args)

    @classmethod
    def _renew_lock(
        cls,
        redis,
        lock_key: str,
        lock_token: str,
        lock_ttl: int,
        stop: Event,
    ) -> None:
        interval = max(0.1, lock_ttl / 3)
        while not stop.wait(interval):
            try:
                renewed = cls._eval_compare_script(
                    redis,
                    _RENEW_LOCK_SCRIPT,
                    [lock_key],
                    [lock_token, str(lock_ttl)],
                )
                if not renewed:
                    return
            except Exception:
                return

    def delete(self, key: str) -> None:
        """Delete cached data."""
        redis = get_redis()
        if not redis:
            return

        try:
            full_key = f"{self.key_prefix}{key}"
            keys = [full_key]
            if self.stale_ttl is not None:
                keys.append(f"{full_key}:stale")
            redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")

    def clear_prefix(self) -> int:
        """Delete all cached data with this prefix. Returns count deleted."""
        redis = get_redis()
        if not redis:
            return 0

        try:
            # Scan for all keys with this prefix and delete them
            pattern = f"{self.key_prefix}*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=100)
                if keys:
                    redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.warning(f"Redis CLEAR error for {self.key_prefix}: {e}")
            return 0
