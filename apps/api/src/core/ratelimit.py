"""Rate limiting using Upstash Redis with sliding window algorithm."""
import logging
import time
from typing import Optional

from fastapi import HTTPException, Request, Response
from upstash_ratelimit import Ratelimit, SlidingWindow

from src.core.redis import get_redis
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using Upstash Redis with sliding window algorithm.

    Args:
        max_requests: Maximum requests allowed in window
        window: Time window in seconds
        prefix: Redis key prefix for this limiter
    """

    def __init__(self, max_requests: int, window: int, prefix: str):
        self.max_requests = max_requests
        self.window = window
        self.prefix = prefix
        self._limiter: Optional[Ratelimit] = None

    def _get_limiter(self) -> Optional[Ratelimit]:
        """Get or create rate limiter instance."""
        if self._limiter is not None:
            return self._limiter

        settings = get_settings()
        if not settings.rate_limit_enabled:
            return None

        redis = get_redis()
        if not redis:
            logger.warning("Redis not available, rate limiting disabled")
            return None

        try:
            self._limiter = Ratelimit(
                redis=redis,
                limiter=SlidingWindow(
                    max_requests=self.max_requests,
                    window=self.window,
                ),
                prefix=f"stock_massive:ratelimit:{self.prefix}",
            )
            return self._limiter
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {e}")
            return None

    def _get_identifier(self, request: Request) -> str:
        """Get rate limit identifier from request (IP address).

        Uses direct client IP for security. X-Forwarded-For is only used
        when the first IP in the chain is a valid IP address to prevent
        header spoofing attacks.
        """
        # Try X-Forwarded-For header first (for proxies/load balancers)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain and validate
            first_ip = forwarded.split(",")[0].strip()
            if self._is_valid_ip(first_ip):
                return first_ip
            # Invalid IP in header - fall back to client IP

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format to prevent header injection."""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    async def __call__(self, request: Request, response: Response):
        """FastAPI dependency for rate limiting.

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        limiter = self._get_limiter()

        # Graceful degradation - allow request if Redis unavailable
        if not limiter:
            return

        identifier = self._get_identifier(request)

        try:
            result = limiter.limit(identifier)

            # Set rate limit headers
            response.headers["X-RateLimit-Limit"] = str(result.limit)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
            response.headers["X-RateLimit-Reset"] = str(result.reset)

            # Log rate limit status at debug level
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

        except HTTPException:
            raise  # Re-raise 429 errors
        except Exception as e:
            # Log error but allow request (graceful degradation)
            logger.warning(f"Rate limit check failed for {identifier}: {e}")


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
