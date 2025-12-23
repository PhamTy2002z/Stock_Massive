# Brainstorm: Volume Spikes - Top 50 Profitable Companies Filter

**Date:** 2025-12-23
**Status:** Analysis Complete

## Problem Statement

Current `/analytics/volume-spikes` page shows **all** stocks with unusual volume, but most are "garbage" (penny stocks, low-quality companies). User wants to filter volume spikes to only show stocks from **Top 50 most profitable companies** (based on financial statements analysis).

## Current System Analysis

### Data Sources
1. **FinancialStatement** table: Contains ranked list of top 50 companies by net profit (per quarter)
   - Fields: `symbol`, `rank`, `net_profit`, `revenue`, `profit_margin`, `eps`, `exchange`, `year`, `quarter`
   - Already has `rank` column (1-50 ordering)

2. **StockDailyOHLCV** table: Daily price/volume data for volume spike calculation
   - Fields: `symbol`, `trade_date`, `volume`, `close_price`, etc.

3. **Volume spike calculation**: Done in-memory by `AnalyticsService.get_volume_spikes()` method
   - Fetches all OHLCV data, calculates 20-day average, computes spike ratio
   - Groups by ICB industry from vnstock API

### Current API Endpoints
- `GET /api/v1/stocks/analytics/financial-statements` → Returns top 50 companies
- `GET /api/v1/stocks/analytics/volume-spikes` → Returns all volume spikes grouped by industry

### Key Insight
Both data sources already exist. Need to **cross-reference** volume spikes with financial statements to filter.

---

## Evaluated Approaches

### Option A: Backend Filter Parameter (Recommended)

**Description:** Add `top_profitable_only: bool = False` parameter to `/volume-spikes` endpoint.

**Backend Changes:**
```python
# router.py - Add parameter
@router.get("/volume-spikes")
async def get_volume_spikes(
    ...
    top_profitable_only: bool = Query(False, description="Only show Top 50 profitable companies"),
    ...
)

# service.py - Filter logic
async def get_volume_spikes(..., top_profitable_only: bool = False):
    # Get top 50 symbols if filter enabled
    top_symbols = None
    if top_profitable_only:
        top_query = select(FinancialStatement.symbol).where(
            FinancialStatement.rank <= 50
        ).order_by(FinancialStatement.rank.asc())
        result = await self.db.execute(top_query)
        top_symbols = {row.symbol for row in result.all()}

    # In spike calculation loop, skip symbols not in top_symbols
    if top_symbols and symbol not in top_symbols:
        continue
```

**Frontend Changes:**
```tsx
// Add toggle/tab in VolumeSpikeDashboard
const [topProfitableOnly, setTopProfitableOnly] = useState(false)

useVolumeSpikes({
  minRatio,
  exchange,
  includeUpcom,
  topProfitableOnly,  // New param
})
```

**Pros:**
- Simple, minimal code changes
- Single API call, efficient
- Reuses existing cache structure (add to cache key)
- Maintains current UI flow

**Cons:**
- Slightly more complex backend logic
- Need to handle period mismatch (latest financial quarter vs today's volume)

**Effort:** Low (~2-3 hours)

---

### Option B: Dedicated New Endpoint

**Description:** Create new endpoint `/volume-spikes/top-profitable` that only returns spikes for top 50.

**Backend:**
```python
@router.get("/volume-spikes/top-profitable")
async def get_top_profitable_volume_spikes(...):
    # Dedicated endpoint logic
```

**Pros:**
- Clean separation of concerns
- Easier to test independently
- Different caching strategy possible

**Cons:**
- More code duplication (or need shared helper)
- Frontend needs to manage two different endpoints
- Violates DRY if not carefully refactored

**Effort:** Medium (~3-4 hours)

---

### Option C: Frontend-Only Filter (Client-Side Join)

**Description:** Fetch both financial statements and volume spikes, filter on frontend.

**Frontend:**
```tsx
const { data: financials } = useFinancialStatements(50)
const { data: spikes } = useVolumeSpikes(...)

const top50Symbols = new Set(financials?.data.map(f => f.symbol) || [])

// Filter industries to only include top 50 stocks
const filteredIndustries = spikes?.industries.map(group => ({
  ...group,
  stocks: group.stocks.filter(s => top50Symbols.has(s.symbol))
})).filter(g => g.stocks.length > 0)
```

**Pros:**
- No backend changes needed
- Quick to implement
- Flexible for other frontend-only filters

**Cons:**
- Fetches all volume spike data (wasteful bandwidth)
- Two API calls required
- Filter logic duplicated if needed elsewhere
- Less efficient for large datasets

**Effort:** Low (~1-2 hours) but suboptimal architecture

---

## Recommendation: Option A (Backend Filter Parameter)

### Rationale
1. **KISS:** Single parameter addition, minimal code
2. **Efficiency:** Backend filters before sending response → less data over wire
3. **Caching:** Easy to add `top_profitable_only` to cache key
4. **Reusability:** Other clients can use same filter
5. **No Code Duplication:** Same endpoint, just conditional logic

### Implementation Plan

#### Phase 1: Backend (1.5 hours)
1. Update `VolumeSpikeParams` schema to include `top_profitable_only: bool`
2. Modify `AnalyticsService.get_volume_spikes()`:
   - Query `FinancialStatement` table for top 50 symbols (latest period)
   - Skip symbols not in top 50 during spike calculation
3. Update cache key to include new parameter
4. Add unit test for new filter

#### Phase 2: Frontend (1.5 hours)
1. Update `lib/api.ts` - add `topProfitableOnly` to params
2. Update `use-volume-spikes.ts` hook
3. Add **Tab** or **Toggle** in `VolumeSpikeDashboard`:

**UI Option 1: Tabs (Recommended)**
```
[ Tất cả | Top 50 Lợi nhuận ]
```
- Clean separation
- User understands context immediately
- Easy to switch

**UI Option 2: Checkbox/Toggle**
```
[x] Chỉ Top 50 LN cao nhất
```
- More compact
- Works with existing filter row

---

## UI/UX Recommendations

### Confirmed: Tab-based Filter with Top 50 as Default

```
Tabs: [ Top 50 LN (default) | Tất cả HOSE/HNX ]

Default view: "Top 50 LN"
- Header: "Khối lượng đột biến - Top 50 Lợi nhuận"
- Subheader: "Chỉ hiển thị CP từ 50 công ty có lợi nhuận cao nhất"
- This is the PRIMARY view users care about

Secondary tab: "Tất cả HOSE/HNX"
- Header: "Khối lượng đột biến - Tất cả"
- Shows all stocks (including "garbage")
- For users who want complete market view
```

### Tab Implementation
```tsx
<Tabs defaultValue="top50" ...>
  <TabsList>
    <TabsTrigger value="top50">Top 50 LN</TabsTrigger>
    <TabsTrigger value="all">Tất cả</TabsTrigger>
  </TabsList>
  <TabsContent value="top50">
    {/* Volume spikes with topProfitableOnly=true */}
  </TabsContent>
  <TabsContent value="all">
    {/* Current implementation */}
  </TabsContent>
</Tabs>
```

### Empty State for Top 50
```
Không có cổ phiếu Top 50 nào đạt ngưỡng đột biến hôm nay.
→ Xem tab "Tất cả" để xem toàn bộ thị trường.
```

---

## Technical Considerations

### 1. Period Alignment
Financial statements are quarterly. Volume spikes are daily. Current approach uses **latest available quarter** data, which is correct.

### 2. Performance
- Top 50 query is simple SELECT with index on `rank`
- Set lookup O(1) per symbol
- No significant performance impact

### 3. Caching
Current cache key pattern:
```
{date}:{min_ratio}:{exchange}:{include_upcom}:{limit}
```
New pattern:
```
{date}:{min_ratio}:{exchange}:{include_upcom}:{limit}:{top_profitable_only}
```

### 4. Edge Cases
- Empty financial statements table → Return empty (already handled)
- Top 50 symbols with no OHLCV data → Already skipped
- Mix of exchanges → Works with existing exchange filter

---

## Next Steps

1. **Confirm approach** with user
2. Create implementation plan with phases
3. Implement backend filter
4. Implement frontend tab
5. Test edge cases
6. Update documentation

---

## Confirmed Decisions

1. **Tab placement:** Data source tabs (Top 50 / Tất cả) placed **ABOVE** filters. Chart tabs remain below.
2. **Exchange filter in Top 50:** NOT needed - just follow Top 50 list regardless of exchange
3. **Default tab:** "Top 50 LN" is the default view
4. **Exchange filter in "Tất cả":** Keep existing behavior

## Final UI Layout

```
┌─────────────────────────────────────────────────┐
│ Khối lượng đột biến - Top 50 Lợi nhuận          │
│ 2024-12-23 • 12 cổ phiếu                    [↻] │
├─────────────────────────────────────────────────┤
│ [ Top 50 LN ✓ ] [ Tất cả ]  ← DATA SOURCE TABS  │
├─────────────────────────────────────────────────┤
│ Ngưỡng: [≥1.5x ▼]           ← FILTERS          │
│ (No exchange filter in Top 50 mode)             │
├─────────────────────────────────────────────────┤
│ Summary Cards (3 cards)                         │
├─────────────────────────────────────────────────┤
│ [ Cột ngang | Tròn | Phân cấp | KL vs Giá ]    │
│ ← CHART TABS (unchanged)                        │
├─────────────────────────────────────────────────┤
│ Chart content                                   │
├─────────────────────────────────────────────────┤
│ Industry groups (collapsible)                   │
└─────────────────────────────────────────────────┘
```

## Ready for Implementation

No unresolved questions remaining.
