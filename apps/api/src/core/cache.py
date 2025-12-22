"""Generic trading-hours-aware cache for stock market data."""
import json
import logging
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.core.redis import get_redis

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


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
    ):
        self.key_prefix = key_prefix
        self.ttl_trading = ttl_trading
        self.ttl_off_hours = ttl_off_hours

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

    def set(self, key: str, value: Any) -> None:
        """Store data in Upstash Redis with dynamic TTL."""
        redis = get_redis()
        if not redis:
            return

        try:
            full_key = f"{self.key_prefix}{key}"
            ttl = self._get_ttl()
            # Serialize to JSON and set with expiration
            redis.set(full_key, json.dumps(value, default=str), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}")

    def delete(self, key: str) -> None:
        """Delete cached data."""
        redis = get_redis()
        if not redis:
            return

        try:
            full_key = f"{self.key_prefix}{key}"
            redis.delete(full_key)
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
