"""Company domain schemas."""

from typing import Literal, Optional

from pydantic import BaseModel

from .common import StrictModel


class CompanyOverview(StrictModel):
    """Company overview information."""

    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None
    established_year: Optional[int] = None
    employees: Optional[int] = None
    website: Optional[str] = None
    description: Optional[str] = None


class StockSymbol(StrictModel):
    """Stock symbol listing."""

    symbol: str
    organ_name: Optional[str] = None
    exchange: Optional[str] = None
    organ_type_code: Optional[str] = None


class StockDetail(StrictModel):
    """Comprehensive stock detail data combining price, company, and financial info.

    Units, since the upstream providers disagree and the payload mixes them:
    every price field is plain VND, ``trading_value`` is millions of VND, and
    ``market_cap`` is billions of VND.
    """

    # Basic Info
    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None

    # Real-time Price Data
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    ceiling: Optional[float] = None
    floor: Optional[float] = None
    ref_price: Optional[float] = None

    # Intraday Range
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None

    # Volume & Value
    volume: Optional[int] = None
    trading_value: Optional[float] = None  # Million VND

    # Market Cap & Shares
    market_cap: Optional[float] = None  # Billion VND
    outstanding_shares: Optional[float] = None
    issue_share: Optional[float] = None

    # 52-Week Data
    high_52_week: Optional[float] = None
    low_52_week: Optional[float] = None
    avg_volume_52_week: Optional[int] = None

    # Financial Ratios
    eps: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    beta: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None

    # Company Details
    description: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    established_year: Optional[int] = None

    # VN30 Ranking
    vn30_rank: Optional[int] = None  # Rank by market cap within VN30 (1-30), None if not in VN30


# === Shareholders Schemas ===


class ShareholderItem(StrictModel):
    """Major shareholder data."""

    id: str
    name: str
    shares: float  # Number of shares
    ownership_pct: float  # Ownership percentage (0-100)
    update_date: Optional[str] = None


class ShareholdersResponse(StrictModel):
    """Response for shareholders endpoint."""

    symbol: str
    shareholders: list[ShareholderItem]
    total_count: int


class OfficerItem(StrictModel):
    """Company officer/insider data."""

    id: str
    name: str
    position: str
    position_short: Optional[str] = None
    shares: Optional[float] = None  # Number of shares
    ownership_pct: Optional[float] = None  # Ownership percentage
    update_date: Optional[str] = None
    status: Optional[str] = None  # working/resigned


class OfficersResponse(StrictModel):
    """Response for officers endpoint."""

    symbol: str
    officers: list[OfficerItem]
    total_count: int


class InsiderDealItem(StrictModel):
    """Insider trading deal data."""

    announce_date: str
    action: str  # Mua/Bán
    quantity: float
    price: Optional[float] = None
    ratio: Optional[float] = None


class InsiderDealsResponse(StrictModel):
    """Response for insider deals endpoint."""

    symbol: str
    deals: list[InsiderDealItem]
    total_count: int


# === News & Dividends Schemas ===


class NewsItem(StrictModel):
    """One news article, whether a corporate disclosure or a press story."""

    # A string because no source guarantees an integer: VCI's `id` column is a
    # hex digest and CafeF's key is the digit run at the end of its slug.
    # Coercing to int used to fail and fall back to the row's position, which
    # renamed an article whenever the feed shifted under it.
    id: str
    title: str
    source: Optional[str] = None
    published_at: str
    price: Optional[float] = None
    price_change_pct: Optional[float] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None  # Feed slug, absent on the per-symbol lane


class NewsResponse(StrictModel):
    """Response for company news endpoint."""

    symbol: str
    items: list[NewsItem]
    total_count: int


class NewsCategory(StrictModel):
    """One facet of the press feed: the slug served and its Vietnamese label."""

    slug: str
    label: str


class FeedNewsItem(NewsItem):
    """One feed entry.

    `symbol` is optional because a press article belongs to a category, not to a
    ticker; only the per-symbol lane can fill it in.
    """

    symbol: Optional[str] = None


class NewsFeedResponse(StrictModel):
    """Press news for one category, newest first."""

    items: list[FeedNewsItem]
    category: str  # The slug actually served
    categories: list[NewsCategory]  # The full registry, for the UI's pill row
    # Kept for the per-symbol lane; empty on the press feed, which has no
    # ticker to attribute an article to.
    symbols: list[str]
    generated_at: str  # ISO timestamp, Asia/Ho_Chi_Minh
    total_count: int


class ArticleBlock(StrictModel):
    """One block of an article's body, in reading order.

    A block tree rather than one string because the reader draws prose, a
    subheading, a pull quote and a photo differently, and flattening them to
    text throws away the only signal that says which is which. Every field but
    `kind` is optional and only the ones that field implies are populated:
    `text` for prose, `items` for a list, `image_url` plus `caption` for a
    figure. `NewsArticleResponse.content` carries the flattened form for callers
    that want plain text.
    """

    kind: Literal["paragraph", "heading", "quote", "list", "image"]
    text: Optional[str] = None
    items: Optional[list[str]] = None
    image_url: Optional[str] = None
    caption: Optional[str] = None


class NewsArticleResponse(StrictModel):
    """One press article's body, read from the publisher's own page.

    Separate from the feed rather than a field on `FeedNewsItem`: the body costs
    one HTTP request per article, and folding it into the feed would turn a
    single request per category rebuild into one per headline nobody opened.
    """

    url: str
    source: str
    blocks: list[ArticleBlock]
    # The same body as newline-separated plain text, matching what
    # `NewsItem.content` is declared to hold everywhere else.
    content: str


class DividendItem(StrictModel):
    """Dividend history item."""

    exercise_date: str
    year: int
    dividend_pct: float  # e.g., 18.1 for 18.1%
    method: str  # 'cash' or 'share'


class DividendsResponse(StrictModel):
    """Response for dividends endpoint."""

    symbol: str
    items: list[DividendItem]
    total_count: int


# === Advanced Deep Dive Schemas ===


class RatioSummaryResponse(StrictModel):
    """Financial ratios summary for advanced tab."""

    symbol: str
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
