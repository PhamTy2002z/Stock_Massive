"""Redis-backed fixed-window API rate limiting, with an in-process fallback."""
import asyncio
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import ipaddress
import logging
import math
import threading
import time
from typing import Any, Optional

from fastapi import HTTPException, Request, Response

from src.core.redis import get_redis
from src.core.config import get_settings

logger = logging.getLogger(__name__)

_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
_IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset: int


class RedisFixedWindowLimiter:
    """Small limiter compatible with both redis-py and Upstash clients.

    Synchronous: both clients are. Async callers run it through
    ``asyncio.to_thread`` so a slow Redis never stalls the event loop.
    """

    def __init__(self, redis: Any, max_requests: int, window: int, prefix: str):
        self.redis = redis
        self.max_requests = max_requests
        self.window = window
        self.prefix = prefix

    def limit(self, identifier: str) -> RateLimitResult:
        now = int(time.time())
        bucket = now // self.window
        reset = (bucket + 1) * self.window
        key = f"{self.prefix}:{identifier}:{bucket}"
        current = int(self.redis.incr(key))
        if current == 1:
            self.redis.expire(key, self.window + 1)
        return RateLimitResult(
            allowed=current <= self.max_requests,
            limit=self.max_requests,
            remaining=max(0, self.max_requests - current),
            reset=reset,
        )


class InProcessSlidingWindowLimiter:
    """The limit a fail-closed scope keeps when Redis is absent or erroring.

    Per process, so N API workers allow up to N times the limit; that is still a
    limit, where failing open is none, and it is better for a real user than a
    blanket 503. Memory is bounded by ``max_keys``.
    """

    def __init__(self, max_requests: int, window: int, max_keys: int = 10_000):
        self.max_requests = max_requests
        self.window = window
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def limit(self, identifier: str) -> RateLimitResult:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(identifier)
            if hits is None:
                if len(self._hits) >= self.max_keys:
                    self._make_room(now)
                hits = self._hits[identifier] = deque()
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            allowed = len(hits) < self.max_requests
            # A refused attempt is not recorded, so hammering does not extend
            # the caller's own lockout past one window.
            if allowed:
                hits.append(now)
            oldest = hits[0] if hits else now
            reset = int(time.time() + math.ceil(oldest + self.window - now))
            return RateLimitResult(
                allowed=allowed,
                limit=self.max_requests,
                remaining=max(0, self.max_requests - len(hits)),
                reset=reset,
            )

    def _make_room(self, now: float) -> None:
        cutoff = now - self.window
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]
        # ponytail: evicts the oldest-inserted key when every key is live, so a
        # caller spraying max_keys addresses can reset one victim's window; an
        # LRU or a smaller window fixes that if it ever matters.
        while len(self._hits) >= self.max_keys:
            del self._hits[next(iter(self._hits))]


@lru_cache(maxsize=4)
def _trusted_networks(raw: str) -> tuple[_IPNetwork, ...]:
    return tuple(ipaddress.ip_network(c.strip()) for c in raw.split(",") if c.strip())


def _parse_ip(value: str) -> Optional[_IPAddress]:
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    # A dual-stack socket reports an IPv4 peer as ::ffff:a.b.c.d.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _is_trusted(ip: _IPAddress) -> bool:
    return any(ip in net for net in _trusted_networks(get_settings().trusted_proxy_cidrs))


class RateLimiter:
    """FastAPI dependency: a fixed window per client address.

    Args:
        max_requests: Maximum requests allowed in window
        window: Time window in seconds
        prefix: Redis key prefix for this limiter
        fail_closed: When Redis is unavailable or errors, keep limiting with an
            in-process window instead of letting every request through. For
            credential endpoints, where "no limit" means free brute forcing.
    """

    def __init__(self, max_requests: int, window: int, prefix: str, fail_closed: bool = False):
        self.max_requests = max_requests
        self.window = window
        self.prefix = prefix
        self.fail_closed = fail_closed
        self._limiter: Optional[RedisFixedWindowLimiter] = None
        self._fallback = (
            InProcessSlidingWindowLimiter(max_requests, window) if fail_closed else None
        )

    def _get_limiter(self) -> Optional[RedisFixedWindowLimiter]:
        """Get or create rate limiter instance."""
        if self._limiter is not None:
            return self._limiter

        settings = get_settings()
        if not settings.rate_limit_enabled:
            return None

        redis = get_redis()
        if not redis:
            logger.warning("Redis not available for rate limiter %s", self.prefix)
            return None

        try:
            self._limiter = RedisFixedWindowLimiter(
                redis=redis,
                max_requests=self.max_requests,
                window=self.window,
                prefix=f"stock_massive:ratelimit:{self.prefix}",
            )
            return self._limiter
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {e}")
            return None

    def _check_redis(self, identifier: str) -> Optional[RateLimitResult]:
        """Blocking: resolve the Redis limiter and count. None = nothing counted."""
        limiter = self._get_limiter()
        return limiter.limit(identifier) if limiter else None

    def _get_identifier(self, request: Request) -> str:
        """The client address this request is charged to.

        ``X-Forwarded-For`` is believed only when the direct peer is a trusted
        proxy, and then only its right-most untrusted entry: everything left of
        that was written by the client and can say anything. A malformed entry
        ends the walk, since nothing from there leftwards is proxy-written.
        """
        peer_host = request.client.host if request.client else None
        if not peer_host:
            return "unknown"
        peer = _parse_ip(peer_host)
        if peer is None or not _is_trusted(peer):
            return peer_host

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            for hop in reversed(forwarded.split(",")):
                ip = _parse_ip(hop)
                if ip is None:
                    break
                if not _is_trusted(ip):
                    return str(ip)
        return str(peer)

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format to prevent header injection."""
        return _parse_ip(ip) is not None

    async def __call__(self, request: Request, response: Response):
        """FastAPI dependency for rate limiting.

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        if not get_settings().rate_limit_enabled:
            return

        identifier = self._get_identifier(request)

        try:
            # Off the event loop: both Redis clients are synchronous, and the
            # first call may also connect (see core/llm/client.py for the same).
            result = await asyncio.to_thread(self._check_redis, identifier)
        except Exception as e:
            logger.warning(f"Rate limit check failed for {identifier}: {e}")
            result = None

        if result is None:
            if self._fallback is None:
                return  # fail open: this scope prefers availability
            result = self._fallback.limit(identifier)

        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset)
        logger.debug(
            f"Rate limit check: {identifier} - "
            f"{result.remaining}/{result.limit} remaining"
        )

        if not result.allowed:
            retry_after = int(result.reset - time.time())
            logger.warning(
                f"Rate limit exceeded: {identifier} on {request.url.path} - "
                f"retry after {retry_after}s"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Rate limit exceeded. Try again later.",
                    "limit": result.limit,
                    "remaining": result.remaining,
                    "reset": result.reset,
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )


# Global rate limiter instances (use config)
settings = get_settings()

standard_rate_limit = RateLimiter(
    max_requests=settings.rate_limit_standard_max,
    window=settings.rate_limit_standard_window,
    prefix="standard",
)

heavy_rate_limit = RateLimiter(
    max_requests=settings.rate_limit_heavy_max,
    window=settings.rate_limit_heavy_window,
    prefix="heavy",
)

# Register, login and password change. Same allowance as `heavy`, its
# own bucket (an upload no longer spends a login attempt), and fail-closed.
credential_rate_limit = RateLimiter(
    max_requests=settings.rate_limit_heavy_max,
    window=settings.rate_limit_heavy_window,
    prefix="credential",
    fail_closed=True,
)
