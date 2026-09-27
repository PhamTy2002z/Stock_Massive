"""Redis client setup for local Redis or Upstash, and the scripts both speak.

Two client libraries are configured shapes here — a self-hosted Redis locally
and Upstash over REST — and they disagree about how a script is called. That
disagreement belongs in one place: a caller that gets it wrong does not fail
loudly, it falls into the ``except TypeError`` of whichever spelling it wrote
and looks fine until the other client is the one deployed.

The two lock scripts live here for the same reason. A Collector lease and a
cache-refresh lock are the same primitive, and two copies of "delete only if the
token is still mine" are two chances for one of them to become "delete".
"""
import logging
import threading
import time
from typing import Any, Optional

from redis import Redis as StandardRedis
from upstash_redis import Redis as UpstashRedis

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Release only a lock this holder still owns. Deleting unconditionally lets a
# holder whose lease already expired delete its successor's.
RELEASE_IF_OWNED_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

# Extend only a lock this holder still owns, for the same reason.
RENEW_IF_OWNED_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


def eval_script(redis: Any, script: str, keys: list[str], args: list[Any]) -> Any:
    """Run a script against either client this deployment might be using.

    redis-py takes the key count positionally and Upstash takes keyword lists.
    Both are configured, so both are spoken.
    """
    try:
        return redis.eval(script, keys=keys, args=args)
    except TypeError:
        return redis.eval(script, len(keys), *keys, *args)


_redis_client: Optional[Any] = None
# When the last initialisation failed (monotonic seconds), or None. A dead Redis
# is not re-pinged on every call: each ping can cost a full connect timeout, and
# most callers sit on the request path.
_failed_at: Optional[float] = None
_init_lock = threading.Lock()

# Small on purpose. Every command this app sends is O(1) or a short script, so a
# reply slower than this means Redis is unwell, and a caller waiting on it is a
# request (or a worker thread) held hostage by a cache.
SOCKET_TIMEOUT_SECONDS = 1.0
RETRY_AFTER_FAILURE_SECONDS = 30.0


def get_redis() -> Optional[Any]:
    """Get the configured Redis client singleton.

    Returns None if not configured, or if initialisation failed less than
    ``RETRY_AFTER_FAILURE_SECONDS`` ago (graceful degradation).
    """
    global _redis_client, _failed_at

    if _redis_client is not None:
        return _redis_client
    if _failed_at is not None and time.monotonic() - _failed_at < RETRY_AFTER_FAILURE_SECONDS:
        return None

    with _init_lock:
        # Another thread may have finished (or failed) while this one waited.
        if _redis_client is not None:
            return _redis_client
        if _failed_at is not None and time.monotonic() - _failed_at < RETRY_AFTER_FAILURE_SECONDS:
            return None

        settings = get_settings()
        try:
            if settings.cache_redis_url:
                client = StandardRedis.from_url(
                    settings.cache_redis_url,
                    decode_responses=True,
                    socket_timeout=SOCKET_TIMEOUT_SECONDS,
                    socket_connect_timeout=SOCKET_TIMEOUT_SECONDS,
                )
                client.ping()
                logger.info("Standard Redis client initialized")
            elif settings.redis_url and settings.redis_token:
                client = UpstashRedis(
                    url=settings.redis_url,
                    token=settings.redis_token,
                )
                logger.info("Upstash Redis client initialized")
            else:
                logger.warning("Redis not configured, caching disabled")
                return None
        except Exception as e:
            logger.error(
                "Failed to initialize Redis (next attempt in %ss): %s",
                int(RETRY_AFTER_FAILURE_SECONDS),
                e,
            )
            _failed_at = time.monotonic()
            return None
        _redis_client = client
        _failed_at = None
        return _redis_client


def reset_redis_client() -> None:
    """Clear the singleton after configuration changes or in tests."""
    global _redis_client, _failed_at
    _redis_client = None
    _failed_at = None
