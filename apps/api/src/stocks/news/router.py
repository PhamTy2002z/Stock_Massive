"""News feed router.

The feed is a third-party HTTP fetch inside a user's request, so it keeps
`heavy_rate_limit` and a response cache. The TTLs are short by this router's
standards — CafeF publishes minutes-old items and a stale headline reads as a
broken screen — while the day of stale fallback stays: yesterday's news beats a
503 when the site is refusing.

The cache key carries the category. The UI switches facets, and a shared key
would serve whichever one was fetched last under every label.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.cache import TradingHoursCache
from src.core.ratelimit import heavy_rate_limit

from ..providers.cafef_article import is_cafef_article_url
from ..providers.cafef_rss import CafeFUnavailable, category_slugs
from ..schemas.company import NewsArticleResponse, NewsCategory, NewsFeedResponse
from .service import DEFAULT_CATEGORY, get_news_feed_service

news_feed_cache = TradingHoursCache(
    key_prefix="stock:news_feed:",
    ttl_trading=300,
    ttl_off_hours=900,
    stale_ttl=86400,
)

# A published article does not change, so the two TTLs are equal and long:
# nothing about the trading day makes yesterday's body go stale. The point of
# caching it at all is that a reader who opens, backs out and reopens must not
# spend three requests on CafeF for one story.
news_article_cache = TradingHoursCache(
    key_prefix="stock:news_article:",
    ttl_trading=86400,
    ttl_off_hours=86400,
    stale_ttl=604800,
)

router = APIRouter()


@router.get("/news/categories", response_model=list[NewsCategory])
def get_news_categories() -> list[NewsCategory]:
    """The feed's facets. A static registry — no network, nothing to cache.

    Separate from the feed so the pill row does not have to fetch 120 articles
    to learn what it should render.
    """
    return get_news_feed_service().get_categories()


@router.get(
    "/news/feed",
    response_model=NewsFeedResponse,
    dependencies=[Depends(heavy_rate_limit)],
)
def get_news_feed(category: str = Query(DEFAULT_CATEGORY)) -> NewsFeedResponse:
    """Get the press news feed for one category, newest item first."""
    slugs = category_slugs()
    if category not in slugs:
        # Validated ahead of the cache so a typo cannot occupy a key of its own.
        raise HTTPException(
            status_code=400,
            detail=f"Unknown news category '{category}'. Valid: {', '.join(slugs)}",
        )

    service = get_news_feed_service()
    payload = news_feed_cache.get_or_load(
        f"cafef:{category}",
        lambda: service.get_feed(category).model_dump(mode="json"),
        suppress_failure=lambda exc: isinstance(exc, CafeFUnavailable),
    )
    return NewsFeedResponse.model_validate(payload)


@router.get(
    "/news/article",
    response_model=NewsArticleResponse,
    dependencies=[Depends(heavy_rate_limit)],
)
def get_news_article(url: str = Query(...)) -> NewsArticleResponse:
    """Get one press article's body, as blocks in reading order.

    The URL comes from the client, so it is checked against the reader's own
    allowlist before anything is fetched — without that this route is an open
    proxy to any address a caller names. The check runs ahead of the cache too,
    so a rejected URL cannot take a key.
    """
    if not is_cafef_article_url(url):
        raise HTTPException(
            status_code=400,
            detail="Only CafeF article URLs can be read through this endpoint.",
        )

    service = get_news_feed_service()
    payload = news_article_cache.get_or_load(
        url,
        lambda: service.get_article(url).model_dump(mode="json"),
        suppress_failure=lambda exc: isinstance(exc, CafeFUnavailable),
    )
    return NewsArticleResponse.model_validate(payload)
