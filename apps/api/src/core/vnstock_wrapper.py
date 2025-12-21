"""Safe wrapper for vnstock library with rate limit protection.

vnstock library calls sys.exit() when rate limited, which crashes the entire
application. This wrapper catches SystemExit and provides exponential backoff
retry logic for resilient data fetching.
"""
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from vnstock import Listing, Vnstock

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Rate limit tracking
_consecutive_failures = 0
_last_failure_time: Optional[float] = None
_FAILURE_RESET_SECONDS = 300  # Reset failure count after 5 min of success


class VnstockRateLimitError(Exception):
    """Raised when vnstock hits rate limit."""

    pass


def _reset_failure_tracking():
    """Reset failure tracking after successful period."""
    global _consecutive_failures, _last_failure_time
    if _last_failure_time and (time.time() - _last_failure_time) > _FAILURE_RESET_SECONDS:
        _consecutive_failures = 0
        _last_failure_time = None


def _record_failure():
    """Record a rate limit failure."""
    global _consecutive_failures, _last_failure_time
    _consecutive_failures += 1
    _last_failure_time = time.time()


def safe_vnstock_call(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    **kwargs,
) -> Optional[T]:
    """Execute vnstock function with SystemExit protection and retry logic.

    Args:
        func: Function to call
        *args: Positional arguments for func
        max_retries: Maximum retry attempts (default 3)
        base_delay: Initial delay in seconds (default 2.0)
        max_delay: Maximum delay cap in seconds (default 60.0)
        **kwargs: Keyword arguments for func

    Returns:
        Function result or None if all retries failed

    Raises:
        VnstockRateLimitError: If rate limit persists after all retries
    """
    _reset_failure_tracking()

    for attempt in range(max_retries + 1):
        try:
            result = func(*args, **kwargs)
            return result

        except SystemExit as e:
            # vnstock calls sys.exit() on rate limit
            _record_failure()
            delay = min(base_delay * (2**attempt), max_delay)

            if attempt < max_retries:
                logger.warning(
                    f"vnstock rate limit (attempt {attempt + 1}/{max_retries + 1}), "
                    f"waiting {delay:.1f}s before retry"
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"vnstock rate limit persisted after {max_retries + 1} attempts, "
                    f"consecutive failures: {_consecutive_failures}"
                )
                raise VnstockRateLimitError(
                    f"Rate limit after {max_retries + 1} attempts"
                ) from e

        except Exception as e:
            # Other exceptions - don't retry
            logger.debug(f"vnstock call failed: {e}")
            return None

    return None


def get_stock_history(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1D",
    source: str = "VCI",
    **retry_kwargs,
) -> Optional[Any]:
    """Safely fetch stock history.

    Args:
        symbol: Stock symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        interval: Data interval (default "1D")
        source: Data source (default "VCI")
        **retry_kwargs: Additional args for safe_vnstock_call

    Returns:
        DataFrame with history or None if failed
    """

    def _fetch():
        stock = Vnstock().stock(symbol=symbol, source=source)
        return stock.quote.history(start=start, end=end, interval=interval)

    try:
        result = safe_vnstock_call(_fetch, **retry_kwargs)
        if result is not None and not result.empty:
            return result
    except VnstockRateLimitError:
        logger.warning(f"Rate limited on {source} for {symbol}")

    return None


def get_all_symbols(**retry_kwargs) -> Optional[list]:
    """Safely fetch all stock symbols.

    Returns:
        List of symbols or None if failed
    """

    def _fetch():
        listing = Listing()
        df = listing.all_symbols()
        return df["symbol"].tolist()

    try:
        return safe_vnstock_call(_fetch, **retry_kwargs)
    except VnstockRateLimitError:
        logger.error("Rate limited when fetching symbol list")
        return None


def get_adaptive_delay(base_delay: float = 1.5) -> float:
    """Get adaptive delay based on recent failure rate.

    Increases delay when consecutive failures detected.

    Args:
        base_delay: Base delay in seconds

    Returns:
        Adjusted delay in seconds
    """
    global _consecutive_failures

    if _consecutive_failures == 0:
        return base_delay
    elif _consecutive_failures < 3:
        return base_delay * 2
    elif _consecutive_failures < 5:
        return base_delay * 4
    else:
        return base_delay * 8  # Max 12 seconds with default base
