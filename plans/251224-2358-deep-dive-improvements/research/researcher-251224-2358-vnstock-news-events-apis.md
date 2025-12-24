# Research: Vnstock News & Events APIs

**Researcher ID**: aa8b433
**Date**: 2024-12-24
**Objective**: Analyze vnstock APIs for News & Events tab implementation

---

## Summary

Vnstock cung cấp 3 APIs qua `company` object (source VCI) để implement News & Events tab:
1. **`company.news()`** - Tin tức công ty với metadata giá stock
2. **`company.dividends()`** - Lịch sử cổ tức
3. **`company.insider_deals()`** - Giao dịch nội bộ (đã exists trong codebase)

APIs không có explicit rate limiting doc nhưng project đã có Redis cache + rate limiting infrastructure (100/60s standard, 20/60s heavy).

---

## API Details

### 1. Company News API

**Method**: `stock.company.news()`

**Parameters**: None (auto-fetches based on symbol)

**Return**: `pandas.DataFrame` với 10-18 columns

**Data Structure (v3 format - 10 cols)**:
```python
{
  'rsi': float64,                    # Relative Strength Index
  'rs': float64,                     # Relative Strength
  'price': float64,                  # Current price (có thể null)
  'price_change': float64,           # Price change
  'price_change_ratio': float64,     # Change ratio
  'price_change_ratio_1m': float64,  # 1 month change
  'id': int64,                       # News ID
  'title': object,                   # News title
  'source': object,                  # News source (e.g., "TCBS")
  'publish_date': object             # Publish datetime
}
```

**Extended format (18 cols)** includes:
- `news_title`, `news_sub_title`, `friendly_sub_title`
- `news_image_url`, `news_source_link`
- `news_short_content`, `news_full_content`
- `created_at`, `updated_at`, `lang_code`
- Price data: `close_price`, `ref_price`, `floor`, `ceiling`, `price_change_pct`

**Usage Example**:
```python
from vnstock import Vnstock

stock = Vnstock().stock(symbol="VCB", source="VCI")
df = stock.company.news()
# Returns ~15 latest news items by default
```

**Notes**:
- Không có page size param → lấy ~15 news items mới nhất
- `price` field có thể null cho một số items
- 2 formats khác nhau (10 cols vs 18 cols) - cần verify version
- News source chủ yếu từ TCBS

---

### 2. Dividends API

**Method**: `stock.company.dividends()`

**Parameters**: None

**Return**: `pandas.DataFrame` với 4 columns

**Data Structure**:
```python
{
  'exercise_date': object,             # Execution date (DD/MM/YY format)
  'cash_year': int64,                  # Year of dividend
  'cash_dividend_percentage': float64, # Dividend % (0.181 = 18.1%)
  'issue_method': object               # 'cash' or 'share'
}
```

**Sample Data**:
```
   exercise_date  cash_year  cash_dividend_percentage issue_method
0       25/07/23       2023                     0.181        share
1       22/12/21       2022                     0.276        share
2       22/12/21       2020                     0.120         cash
```

**Usage**:
```python
stock = Vnstock().stock(symbol="VCB", source="VCI")
df = stock.company.dividends()
# Returns full dividend history (có thể 10-15+ years)
```

**Notes**:
- Trả về full lịch sử (không limit)
- `exercise_date` là string DD/MM/YY → cần parse
- `cash_dividend_percentage` là decimal (0.18 = 18%)
- `issue_method`: "cash" hoặc "share"

---

### 3. Insider Deals API (Existing)

**Method**: `stock.company.insider_deals()`

**Parameters**: None

**Return**: `pandas.DataFrame`

**Status**: ✅ **Already implemented** tại `/apps/api/src/stocks/company/service.py:120-156`

**Existing Implementation**:
```python
def get_insider_deals(self, symbol: str) -> InsiderDealsResponse:
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.insider_deals()
    # Transform to InsiderDealItem with fields:
    # - announcement_date, owner_name, owner_position
    # - deal_method, action, quantity, price, ratio
```

**Data Structure** (từ codebase):
```python
{
  'announcement_date': str,   # Deal announcement date
  'owner_name': str,          # Insider name
  'owner_position': str,      # Position in company
  'deal_method': str,         # Trading method
  'action': str,              # Buy/Sell
  'quantity': float,          # Shares quantity
  'price': float,             # Deal price
  'ratio': float              # Ownership ratio
}
```

**Current Endpoint**: `GET /api/v1/stocks/{symbol}/insider-deals`

---

## Implementation Notes

### Rate Limiting & Caching

**Existing Infrastructure** (từ README):
- **Redis Cache**: Upstash Redis với trading-hours-aware TTL
- **Rate Limits**:
  - Standard: 100 requests/60s
  - Heavy endpoints: 20 requests/60s

**Recommendations**:
1. **News API**: Cache 5-10 mins (tin tức ít thay đổi trong ngắn hạn)
2. **Dividends API**: Cache 24h (lịch sử ít thay đổi)
3. **Insider Deals**: Cache 1-6h (update không thường xuyên)

**Rate Limit Classification**:
- News API → **Standard tier** (100/60s) - lightweight
- Dividends → **Standard tier** - cached long-term
- Insider Deals → **Standard tier** (already applied)

### Data Transformation

**News API**:
```typescript
interface NewsItem {
  id: string;
  title: string;
  content?: string;
  source: string;
  publishedAt: string;
  price?: number;
  priceChange?: number;
  priceChangePct?: number;
}
```

**Dividends API**:
```typescript
interface DividendItem {
  exerciseDate: string;      // ISO format
  year: number;
  dividendPct: number;       // % format (18.1)
  method: 'cash' | 'share';
}
```

### API Integration Pattern

Follow existing pattern tại `apps/api/src/stocks/company/`:

```python
# service.py
def get_company_news(self, symbol: str) -> NewsResponse:
    symbol = validate_symbol(symbol)
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.news()
    # Transform to NewsItem[]

def get_company_dividends(self, symbol: str) -> DividendsResponse:
    symbol = validate_symbol(symbol)
    stock = Vnstock().stock(symbol=symbol, source=self.source)
    df = stock.company.dividends()
    # Transform to DividendItem[]

# router.py
@router.get("/{symbol}/news")
@limiter.limit("100/minute")
@cache_with_rate_limit(expire=300)  # 5 min cache
async def get_news(symbol: str):
    return company_service.get_company_news(symbol)

@router.get("/{symbol}/dividends")
@limiter.limit("100/minute")
@cache_with_rate_limit(expire=86400)  # 24h cache
async def get_dividends(symbol: str):
    return company_service.get_company_dividends(symbol)
```

### Frontend Integration

Tab structure cho `/analytics/deep-dive`:

```tsx
<Tabs defaultValue="overview">
  <TabsList>
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="financials">Financials</TabsTrigger>
    <TabsTrigger value="news">News & Events</TabsTrigger> {/* NEW */}
  </TabsList>

  <TabsContent value="news">
    <NewsEventsTab symbol={symbol} />
  </TabsContent>
</Tabs>
```

Components:
- `NewsEventsTab.tsx` - Container
- `NewsList.tsx` - News cards với price info
- `DividendsTable.tsx` - Dividends history table
- `InsiderDealsTable.tsx` - Reuse existing

---

## Unresolved Questions

1. **News API Format**: Cần verify production trả về 10 cols hay 18 cols? (docs show 2 formats khác nhau)
2. **News Pagination**: API không có page param - giới hạn mặc định là bao nhiêu items?
3. **Dividends Date Format**: `exercise_date` luôn DD/MM/YY hay có thể DD/MM/YYYY?
4. **VCI Source Stability**: Tất cả 3 APIs đều require source="VCI" - có fallback source nào không?
5. **Cache Invalidation**: News cache 5 mins có đủ fresh cho real-time updates?
