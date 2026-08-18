"""Market news feed, served from CafeF's public category RSS.

This replaced a VN30 aggregation over VCI's per-symbol news. That feed carries
corporate disclosures with no prose attached — the right answer to "what did
this issuer announce", the wrong one for a reader screen — and it cost one
upstream call per symbol per rebuild. CafeF costs one HTTP request and returns
press articles with a summary, an image and a link to the original.

The per-symbol VCI lane is untouched and still lives in the company router.
"""

import logging
from datetime import datetime
from functools import lru_cache

from ..providers.cafef_rss import CAFEF_CATEGORIES, fetch_category
from ..providers.normalize import VN_TZ
from ..schemas.company import FeedNewsItem, NewsCategory, NewsFeedResponse
from ..shared import StockServiceError

logger = logging.getLogger(__name__)

DEFAULT_CATEGORY = "moi-nhat"

# A feed longer than this is scroll nobody reaches, and it is all held in cache.
MAX_FEED_ITEMS = 120

# Undated items sort below every dated one rather than being dropped. Aware, so
# the comparison never mixes naive and aware stamps.
_UNDATED = datetime(1970, 1, 1, tzinfo=VN_TZ)


class NewsFeedService:
    """Serve one CafeF category as the market news feed."""

    def get_feed(self, category: str = DEFAULT_CATEGORY) -> NewsFeedResponse:
        """The category's articles, newest first, capped at `MAX_FEED_ITEMS`.

        `CafeFUnavailable` propagates: the route in front chooses between stale
        data and a 503, and flattening the outage here would take that choice
        away from it.
        """
        slug = _resolve_category(category)
        rows = fetch_category(slug)

        items = [FeedNewsItem(**row) for row in rows]
        items.sort(key=_feed_sort_key, reverse=True)
        items = items[:MAX_FEED_ITEMS]

        return NewsFeedResponse(
            items=items,
            category=slug,
            categories=self.get_categories(),
            # A press article belongs to a category, not to a ticker.
            symbols=[],
            generated_at=datetime.now(VN_TZ).isoformat(),
            total_count=len(items),
        )

    def get_categories(self) -> list[NewsCategory]:
        """The facets this API exposes, in the order the UI should show them."""
        return [
            NewsCategory(slug=category.slug, label=category.label)
            for category in CAFEF_CATEGORIES
        ]


def _resolve_category(category: str) -> str:
    """Reject an unknown slug before a request is spent on it."""
    slug = (category or "").strip().lower()
    if slug not in {item.slug for item in CAFEF_CATEGORIES}:
        raise StockServiceError(f"Unknown news category: {category}")
    return slug


def _feed_sort_key(item: FeedNewsItem) -> tuple[int, datetime]:
    """Sort newest first, with undated items last rather than dropped."""
    try:
        stamp = datetime.fromisoformat(item.published_at)
    except ValueError:
        return (0, _UNDATED)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=VN_TZ)
    return (1, stamp)


@lru_cache(maxsize=1)
def get_news_feed_service() -> NewsFeedService:
    """Get or create news feed service instance (thread-safe singleton)."""
    return NewsFeedService()
