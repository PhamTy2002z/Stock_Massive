# Brainstorm: Hiệu Suất Ngành Historical (1W/2W/1M)

## Problem Statement

Thêm section "Hiệu suất ngành trong 1 tuần, 2 tuần, 1 tháng" vào trang Overview, dưới mục "Hiệu suất ngành" hiện tại.

**Constraints:**
- Chỉ sử dụng nguồn VCI (TCBS đã ngưng dịch vụ)
- Chú ý rate limit khi kéo dữ liệu từ vnstock API
- Tận dụng caching strategy hiện có (TradingHoursCache + Upstash Redis)

---

## User Requirements (Confirmed)

| Aspect | Choice |
|--------|--------|
| Chart Type | **Horizontal Bar Chart** - dễ đọc, so sánh trực quan |
| Số ngành hiển thị | **Top 5 tăng + Top 5 giảm** - gọn gàng, focus vào highlights |
| Phương pháp tính | **So sánh giá đóng cửa đầu-cuối kỳ** - đơn giản, ít API calls |
| Data Loading | **Pre-computed via scheduled job** - nhanh khi load |

---

## Evaluated Approaches

### Approach 1: Per-Stock Historical Calculation (❌ Rejected)

**Mô tả:** Lấy historical data cho từng stock, tính % change, aggregate theo ngành.

**Pros:**
- Chính xác nhất (market-cap weighted)

**Cons:**
- Rate limit risk: ~1500+ stocks × 3 periods = 4500+ API calls
- Thời gian xử lý lâu (~10-15 phút cho full scan)
- Không khả thi với vnstock rate limit

### Approach 2: Representative Stock Sampling (⚠️ Alternative)

**Mô tả:** Chọn 5-10 stocks lớn nhất mỗi ngành làm đại diện.

**Pros:**
- Giảm đáng kể API calls (~200 calls)
- Vẫn phản ánh xu hướng ngành

**Cons:**
- Không chính xác bằng full calculation
- Large-cap bias

### Approach 3: VN-Index Sector Components (✅ Recommended)

**Mô tả:** Sử dụng VN30/VN100 components + ICB classification để tính proxy cho sector performance.

**Implementation:**
1. Lấy VN100 symbols (100 stocks lớn nhất)
2. Map với ICB Level 2 classification
3. Fetch historical OHLCV cho VN100 (100 API calls)
4. Tính weighted average % change theo market cap cho mỗi ngành
5. Cache kết quả với TTL dài (24h) vì là historical data

**Pros:**
- Balanced: đủ representative (~5-15 stocks/ngành từ VN100)
- Rate limit friendly: 100 API calls thay vì 1500+
- VN100 covers ~80% market cap của mỗi ngành

**Cons:**
- Chỉ cover stocks trong VN100, không phản ánh small-caps
- Một số ngành có ít đại diện trong VN100

---

## Recommended Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SCHEDULED JOB                             │
│  (Daily at 15:30 VN time - after market close)                  │
│                                                                  │
│  1. Fetch VN100 symbols + ICB mapping                           │
│  2. For each symbol: get historical (30 days) - with delay      │
│  3. Calculate sector performance for 1W/2W/1M                   │
│  4. Store in Redis with 24h TTL                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REDIS CACHE                                  │
│  Key: "sector:historical:performance"                           │
│  TTL: 24 hours (static historical data)                         │
│                                                                  │
│  {                                                               │
│    "generated_at": "2024-12-30T15:30:00",                       │
│    "periods": {                                                  │
│      "1W": [{ icb_code, icb_name, change_pct, ... }],           │
│      "2W": [{ icb_code, icb_name, change_pct, ... }],           │
│      "1M": [{ icb_code, icb_name, change_pct, ... }]            │
│    }                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API ENDPOINT                                 │
│  GET /api/v1/stocks/sector-historical-performance               │
│                                                                  │
│  - Read from Redis cache                                         │
│  - If cache miss: return stale data or trigger job              │
│  - Response: SectorHistoricalPerformanceResponse                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND                                     │
│  SectorHistoricalPerformanceSection component                   │
│                                                                  │
│  - Tab selector: 1W | 2W | 1M                                   │
│  - Horizontal Bar Chart (Recharts BarChart)                     │
│  - Top 5 gainers (green) + Top 5 losers (red)                   │
│  - Responsive: stacked on mobile                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Rate Limit Strategy

```python
# apps/api/src/stocks/market/historical_service.py

import asyncio
from vnstock import Vnstock

BATCH_SIZE = 10  # Process 10 stocks at a time
DELAY_BETWEEN_BATCHES = 1.0  # 1 second delay

async def fetch_historical_with_rate_limit(symbols: list[str], days: int = 30):
    """Fetch historical data with rate limiting."""
    results = {}

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]

        for symbol in batch:
            try:
                stock = Vnstock().stock(symbol=symbol, source='VCI')
                df = stock.quote.history(
                    start=(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
                    end=datetime.now().strftime('%Y-%m-%d')
                )
                results[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        # Rate limit: wait between batches
        if i + BATCH_SIZE < len(symbols):
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)

    return results
```

### Backend Schema

```python
# apps/api/src/stocks/schemas/market.py

class SectorHistoricalItem(BaseModel):
    """Sector historical performance for a specific period."""
    icb_code: str
    icb_name: str
    change_pct: float  # % change from period start to end
    stock_count: int   # Number of VN100 stocks in this sector
    top_gainers: list[str]  # Top 3 gaining symbols
    top_losers: list[str]   # Top 3 losing symbols


class SectorHistoricalPerformanceResponse(BaseModel):
    """Response for sector historical performance."""
    period_1w: list[SectorHistoricalItem]  # Sorted by change_pct desc
    period_2w: list[SectorHistoricalItem]
    period_1m: list[SectorHistoricalItem]
    generated_at: datetime
    data_source: str = "VN100"
```

### Frontend Visualization

```tsx
// apps/web/src/components/dashboard/sector-historical-performance.tsx

// Tab selector for period
const [period, setPeriod] = useState<'1W' | '2W' | '1M'>('1W')

// Horizontal Bar Chart using Recharts
<ResponsiveContainer width="100%" height={400}>
  <BarChart
    layout="vertical"
    data={[...topGainers, ...topLosers]}
    margin={{ left: 100, right: 40 }}
  >
    <XAxis type="number" tickFormatter={(v) => `${v.toFixed(1)}%`} />
    <YAxis type="category" dataKey="icb_name" width={100} />
    <Tooltip content={<CustomTooltip />} />
    <Bar
      dataKey="change_pct"
      fill={(entry) => entry.change_pct >= 0 ? 'hsl(var(--stock-up))' : 'hsl(var(--stock-down))'}
    />
  </BarChart>
</ResponsiveContainer>
```

### UI Mockup (ASCII)

```
┌──────────────────────────────────────────────────────────────────┐
│ Hiệu suất ngành theo thời gian                        [Refresh] │
├──────────────────────────────────────────────────────────────────┤
│  ┌─────┐ ┌─────┐ ┌─────┐                                         │
│  │ 1W  │ │ 2W  │ │ 1M  │   ← Tab selector                       │
│  └─────┘ └─────┘ └─────┘                                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Top 5 ngành tăng                           Top 5 ngành giảm     │
│  ──────────────                             ──────────────       │
│  Ngân hàng      ████████████████  +4.2%     Bất động sản ████ -2.1% │
│  Công nghệ      ███████████████   +3.8%     Xây dựng     ███  -1.8% │
│  Bán lẻ         ████████████      +3.1%     Thép         ██   -1.5% │
│  Bảo hiểm       ███████████       +2.9%     Dầu khí      ██   -1.2% │
│  Thực phẩm      █████████         +2.4%     Hóa chất     █    -0.8% │
│                                                                  │
│  Cập nhật: 30/12/2024 15:30 • Nguồn: VN100                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Implementation Considerations

### 1. Scheduled Job Setup

Sử dụng APScheduler đã có trong project:

```python
# apps/api/src/core/scheduler.py

scheduler.add_job(
    compute_sector_historical_performance,
    trigger="cron",
    hour=15,
    minute=30,
    timezone=VN_TZ,
    id="sector_historical_performance",
    replace_existing=True,
)
```

### 2. Error Handling

- **API failure**: Retry với exponential backoff
- **Partial data**: Vẫn tính với dữ liệu có được, log warning
- **Cache miss**: Return last known data hoặc trigger on-demand job

### 3. Fallback Strategy

Nếu scheduled job fail:
1. Frontend hiển thị "Đang cập nhật..." thay vì error
2. Trigger manual job endpoint cho admin
3. Serve stale cache data nếu có

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VCI rate limit block | Medium | High | Aggressive caching, 1s delay between batches |
| VN100 không đủ representative | Low | Medium | Accept trade-off, document limitation |
| Job timeout (>10 min) | Low | Medium | Async processing, partial caching |
| Stale data (job fail) | Low | Low | Serve stale with warning, manual trigger |

---

## Success Metrics

1. **Performance**: API response < 100ms (cached)
2. **Freshness**: Data updated daily by 16:00
3. **Accuracy**: % change calculation matches manual verification
4. **UX**: Chart renders < 500ms, smooth tab switching

---

## Files to Create/Modify

### Backend (apps/api)
| File | Action |
|------|--------|
| `src/stocks/market/historical_service.py` | **Create** - Historical calculation logic |
| `src/stocks/market/router.py` | **Modify** - Add new endpoint |
| `src/stocks/schemas/market.py` | **Modify** - Add new schemas |
| `src/core/scheduler.py` | **Modify** - Add scheduled job |

### Frontend (apps/web)
| File | Action |
|------|--------|
| `src/components/dashboard/sector-historical-performance.tsx` | **Create** - Main component |
| `src/hooks/use-sector-historical.ts` | **Create** - TanStack Query hook |
| `src/lib/api.ts` | **Modify** - Add API function |
| `src/app/(dashboard)/page.tsx` | **Modify** - Add section to Overview |

---

## Next Steps

1. Tạo implementation plan chi tiết với `/plan`
2. Implement backend service + scheduled job
3. Implement frontend component + hook
4. Integration testing với mock data
5. E2E testing với real VCI data

---

## Unresolved Questions

1. **VN100 vs VN-All**: VN100 có đủ representative cho tất cả 18 ngành ICB Level 2 không? Cần verify.
2. **Holiday handling**: Khi thị trường nghỉ lễ, job có nên skip không?
3. **Weekend data**: Period 1W tính từ T-7 hay T-5 trading days?
