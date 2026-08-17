"""Market-wide news feed assembled from per-symbol company news.

No provider serves a market feed, so one is built by asking a bounded set of
symbols for their own news and merging the answers. That makes a single rebuild
cost up to `FEED_SYMBOL_LIMIT` upstream calls, which is why the symbol set is
capped rather than following the whole VN30, and why the route in front of this
is cached hard.
"""

import logging
from datetime import datetime
from functools import lru_cache

from src.core.vnstock_client import Listing, VnstockUnavailable, VnstockUnsupported

from ..company import get_company_service
from ..providers.normalize import VN_TZ
from ..schemas.company import FeedNewsItem, NewsFeedResponse
from ..shared import StockServiceError

logger = logging.getLogger(__name__)

# Each symbol costs one upstream call per rebuild; twelve is what the quota
# tolerates at the TTL the route caches on.
FEED_SYMBOL_LIMIT = 12

# A feed longer than this is scroll nobody reaches, and it is all held in cache.
MAX_FEED_ITEMS = 120

_FEED_DATE_FORMAT = "%Y-%m-%d %H:%M"


class NewsFeedService:
    """Aggregate company news across the VN30 constituents into one feed."""

    def __init__(self, source: str = "VCI"):
        """Initialize news feed service with data source."""
        self.source = source

    def get_feed(self) -> NewsFeedResponse:
        """Build the market-wide news feed, newest item first."""
        symbols = self._feed_symbols()
        company_service = get_company_service(self.source)

        items: list[FeedNewsItem] = []
        served: list[str] = []
        unavailable: VnstockUnavailable | None = None

        for symbol in symbols:
            try:
                response = company_service.get_company_news(symbol)
            except VnstockUnavailable as e:
                # The allowance is spent. Every further symbol would only burn
                # the retry window without returning anything.
                unavailable = e
                break
            except (VnstockUnsupported, StockServiceError) as e:
                logger.warning(f"Skipping {symbol} in news feed: {e}")
                continue

            if not response.items:
                continue

            items.extend(
                FeedNewsItem(symbol=symbol, **item.model_dump())
                for item in response.items
            )
            served.append(symbol)

        if not items and unavailable is not None:
            # Nothing was gathered before the quota ran out, so there is no
            # partial feed to serve and the caller must hear about the outage.
            raise unavailable

        items.sort(key=_feed_sort_key, reverse=True)
        items = items[:MAX_FEED_ITEMS]

        return NewsFeedResponse(
            items=items,
            symbols=served,
            generated_at=datetime.now(VN_TZ).isoformat(),
            total_count=len(items),
        )

    def _feed_symbols(self) -> list[str]:
        """The symbols the feed is built from, capped at `FEED_SYMBOL_LIMIT`."""
        try:
            symbols = Listing().symbols_by_group("VN30")
            if symbols is None:
                raise ValueError("provider returned no VN30 constituents")

            resolved = [
                str(symbol)
                for symbol in (
                    symbols.tolist() if hasattr(symbols, "tolist") else list(symbols)
                )
            ]
            if not resolved:
                raise ValueError("provider returned no VN30 constituents")

            return resolved[:FEED_SYMBOL_LIMIT]
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error listing news feed symbols: {e}")
            raise StockServiceError(f"Failed to list news feed symbols: {e}")


def _feed_sort_key(item: FeedNewsItem) -> datetime:
    """Sort newest first, with undated items last rather than dropped."""
    try:
        return datetime.strptime(item.published_at, _FEED_DATE_FORMAT)
    except ValueError:
        return datetime.min


@lru_cache(maxsize=1)
def get_news_feed_service(source: str = "VCI") -> NewsFeedService:
    """Get or create news feed service instance (thread-safe singleton)."""
    return NewsFeedService(source=source)
