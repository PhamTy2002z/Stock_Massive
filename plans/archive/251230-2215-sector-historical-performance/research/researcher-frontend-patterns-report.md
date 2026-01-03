# Frontend Patterns Research Report
**Date:** 2025-12-30
**Focus:** Sector Historical Performance Component
**Analyzed Components:** volume-spike-chart.tsx, use-volume-spikes.ts, api.ts

---

## 1. Existing Chart Patterns

### Recharts Horizontal BarChart Structure
**From:** `volume-spike-chart.tsx`

```tsx
// Core pattern: ResponsiveContainer > BarChart (layout="vertical")
<ResponsiveContainer width="100%" height={300}>
  <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
    <XAxis type="number" tick={{ fontSize: 11 }} />
    <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={120} />
    <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
    <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={24}>
      {chartData.map((entry, idx) => <Cell key={`cell-${idx}`} fill={getBarColor(entry)} />)}
    </Bar>
  </BarChart>
</ResponsiveContainer>
```

**Key Patterns:**
- `layout="vertical"` for horizontal bars
- Dynamic bar colors via `<Cell>` mapping
- Custom tooltips using Card components
- `memo()` optimization with `isEqual()` comparison
- `isPlaceholderData` prop to disable animations during loading
- Skeleton loader component exported alongside main component

**Color Strategy:**
```tsx
// Dynamic color based on value intensity
function getBarColor(value: number, maxValue: number): string {
  const ratio = value / maxValue
  if (ratio > 0.7) return "hsl(0 84% 60%)"   // Red (high)
  if (ratio > 0.4) return "hsl(25 95% 53%)"  // Orange (medium)
  return "hsl(45 93% 47%)"                   // Yellow (low)
}
```

---

## 2. TanStack Query Hook Patterns

### Hook Structure
**From:** `use-volume-spikes.ts`

```tsx
export function useVolumeSpikes(params: VolumeSpikeParams = {}) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.volumeSpikes(params),
    queryFn: () => fetchVolumeSpikes(params),
    staleTime: 2 * 60 * 1000,              // 2 minutes
    refetchInterval: 3 * 60 * 1000,        // 3 minutes
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })
  return { data, isFetching, refetch }
}
```

**Standard Conventions:**
- `useSuspenseQuery` for data guaranteed to exist (no loading states needed)
- Centralized `queryKeys` from `@/lib/query-keys`
- 2-min staleTime, 3-min auto-refetch interval
- Returns destructured `{ data, isFetching, refetch }`
- Data is ALWAYS defined (no null checks needed in consuming components)

---

## 3. API Client Patterns

### Request Function Structure
**From:** `api.ts`

```tsx
// Generic fetch wrapper
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers }
  })
  if (!response.ok) throw new ApiError(response.status, `API error: ${response.statusText}`)
  return response.json()
}

// Endpoint function pattern
export async function fetchSectorPerformance(): Promise<SectorPerformanceResponse> {
  return fetchApi<SectorPerformanceResponse>("/stocks/sector-performance")
}
```

**Interface Patterns:**
- Response types define exact API shape (snake_case backend → camelCase frontend)
- Transformation happens in endpoint functions when needed
- Params use `URLSearchParams` for query string building
- Custom `ApiError` class for error handling

**Existing Sector Performance API:**
```tsx
export interface SectorPerformanceItem {
  icb_code: string
  icb_name: string
  change_pct: number
  total_market_cap: number
  stock_count: number
  top_gainers: string[]
  top_losers: string[]
}

export interface SectorPerformanceResponse {
  sectors: SectorPerformanceItem[]
  generated_at: string
  total_sectors: number
}
```

---

## 4. Recommended Approach

### Component Architecture
```
sector-historical-performance/
├── sector-historical-performance-chart.tsx   # Main bar chart component
├── sector-historical-performance-tabs.tsx    # Tab selector wrapper
└── Skeleton component pattern
```

### Implementation Steps

**1. Hook Pattern (use-sector-historical-performance.ts)**
```tsx
export function useSectorHistoricalPerformance(period: '1W' | '2W' | '1M') {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    staleTime: 5 * 60 * 1000,  // 5 minutes (historical data changes slower)
    refetchInterval: 10 * 60 * 1000,
    refetchOnWindowFocus: true,
  })
  return { data, isFetching, refetch }
}
```

**2. API Client Extension (api.ts)**
```tsx
export type SectorPeriod = '1W' | '2W' | '1M'

export interface SectorHistoricalItem {
  icb_code: string
  icb_name: string
  change_pct: number
  is_gainer: boolean  // Backend determines top 5 gainers/losers
}

export interface SectorHistoricalResponse {
  period: SectorPeriod
  top_gainers: SectorHistoricalItem[]  // Top 5
  top_losers: SectorHistoricalItem[]   // Top 5
  generated_at: string
}

export async function fetchSectorHistoricalPerformance(
  period: SectorPeriod
): Promise<SectorHistoricalResponse> {
  return fetchApi<SectorHistoricalResponse>(
    `/stocks/analytics/sector-historical?period=${period}`
  )
}
```

**3. Chart Component Pattern**
- Combine `top_gainers` (green) + `top_losers` (red) into single `chartData` array
- Sort by `change_pct` descending (gainers at top)
- Use green for positive `change_pct`, red for negative
- Custom tooltip shows: Sector name, Change %, Period
- Memo optimization with `isEqual()` on data + period
- Export skeleton alongside main component

**4. Tab Component**
```tsx
// Use Shadcn Tabs component
<Tabs defaultValue="1W" onValueChange={setPeriod}>
  <TabsList>
    <TabsTrigger value="1W">1 Tuần</TabsTrigger>
    <TabsTrigger value="2W">2 Tuần</TabsTrigger>
    <TabsTrigger value="1M">1 Tháng</TabsTrigger>
  </TabsList>
  <TabsContent value={period}>
    <SectorHistoricalPerformanceChart data={data} period={period} />
  </TabsContent>
</Tabs>
```

---

## 5. Key Differences vs Volume Spike Pattern

| Aspect | Volume Spike | Sector Historical |
|--------|--------------|-------------------|
| Color logic | Intensity-based (3 colors) | Binary (green/red) |
| Data grouping | Top 10 sectors | Top 5 gainers + Top 5 losers |
| Sorting | By count descending | By change_pct descending |
| Interactivity | None | Tab selector for periods |
| Refetch interval | 3 minutes (real-time) | 10 minutes (historical) |

---

## 6. Missing Dependencies

**Check if these exist:**
- `@/lib/query-keys` - needs `sectorHistoricalPerformance` function
- Shadcn `Tabs` component - verify installed

**Backend Requirement:**
- New endpoint: `GET /stocks/analytics/sector-historical?period={1W|2W|1M}`
- Should return top 5 gainers + top 5 losers pre-sorted

---

## Unresolved Questions

1. **Backend status:** Does `/stocks/analytics/sector-historical` endpoint exist? Need API contract verification.
2. **Query keys:** Where is `@/lib/query-keys` defined? Need to check structure for new key.
3. **Tabs component:** Is `@/components/ui/tabs` already imported from Shadcn?
4. **Data sorting:** Should frontend sort or backend? (Recommend backend sorts, frontend just displays)
5. **Period format:** Confirm backend accepts '1W'/'2W'/'1M' or needs days (7/14/30)?
