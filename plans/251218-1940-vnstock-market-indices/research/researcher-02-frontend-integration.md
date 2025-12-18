# Frontend Integration Research

## Current State

### Existing Components
1. `market-indices.tsx` - Container component with mock data
2. `stock-index-card.tsx` - Card component displaying index info + sparkline

### Mock Data Structure (to replace)
```typescript
{
  symbol: "VNINDEX",
  name: "VN-INDEX",
  value: 1284.23,
  change: 12.45,
  changePercent: 0.98,
  chartData: [1270, 1275, 1268, 1280, ...]
}
```

### Components Ready
- `StockIndexCard` - Fully implemented, accepts props
- `Sparkline` - Chart component ready
- `Skeleton` - Loading state ready

## Integration Requirements

### 1. API Response Type
```typescript
interface MarketIndex {
  symbol: string
  name: string
  value: number
  change: number
  changePercent: number
  chartData: number[]
}
```

### 2. Data Fetching Options
**Option A: React Query (Recommended)**
```typescript
const { data, isLoading } = useQuery({
  queryKey: ['market-indices'],
  queryFn: () => fetch('/api/v1/indices').then(r => r.json()),
  refetchInterval: 60000 // Refresh every minute
})
```

**Option B: SWR**
```typescript
const { data, isLoading } = useSWR('/api/v1/indices', fetcher)
```

**Option C: Server Component + fetch**
```typescript
async function getIndices() {
  const res = await fetch(`${API_URL}/api/v1/indices`, { next: { revalidate: 60 } })
  return res.json()
}
```

### 3. Current Dependencies
- No data fetching library installed yet
- Using Next.js App Router (can use Server Components)

## Recommendation
Use native `fetch` in Server Component for initial load, with client-side refresh via `useEffect` + `setInterval` for real-time updates.

## Files to Modify
1. `apps/web/src/components/dashboard/market-indices.tsx` - Replace mock with API call
2. `apps/api/src/stocks/router.py` - Add `/indices` endpoint
3. `apps/api/src/stocks/service.py` - Add `get_market_indices()` method
4. `apps/api/src/stocks/schemas.py` - Add `MarketIndex` schema
