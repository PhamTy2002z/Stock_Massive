# Phase 02: Frontend Integration

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: Phase 01 (Backend API)
- **Docs**: [code-standards.md](../../docs/code-standards.md)

## Overview
- **Date**: 2024-12-18
- **Priority**: High
- **Implementation Status**: Pending
- **Review Status**: Pending

## Key Insights
- UI components already exist (`StockIndexCard`, `Sparkline`)
- Currently using mock data in `market-indices.tsx`
- Next.js App Router - can use Server Components or client fetch

## Requirements
1. Replace mock data with real API call
2. Show loading skeleton during fetch
3. Handle API errors gracefully
4. Auto-refresh data periodically (optional)

## Architecture
```
MarketIndices (component)
    ↓
fetch('/api/v1/indices')
    ↓
StockIndexCard × 4
```

## Related Code Files
- `apps/web/src/components/dashboard/market-indices.tsx` - Main component
- `apps/web/src/app/(dashboard)/layout.tsx` - Dashboard layout (if needed)

## Implementation Steps

### Step 1: Add API Types
**File**: `apps/web/src/components/dashboard/market-indices.tsx`
```typescript
interface MarketIndex {
  symbol: string
  name: string
  value: number
  change: number
  change_percent: number
  chart_data: number[]
}
```

### Step 2: Add Fetch Function
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchMarketIndices(): Promise<MarketIndex[]> {
  const res = await fetch(`${API_BASE}/api/v1/indices`, {
    next: { revalidate: 60 } // Cache for 60 seconds
  })
  if (!res.ok) throw new Error('Failed to fetch indices')
  return res.json()
}
```

### Step 3: Update Component (Client Component Approach)
```typescript
"use client"

import { useEffect, useState } from "react"
import { StockIndexCard } from "./stock-index-card"
import { Skeleton } from "@/components/ui/skeleton"

interface MarketIndex {
  symbol: string
  name: string
  value: number
  change: number
  change_percent: number
  chart_data: number[]
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function MarketIndices({ className }: { className?: string }) {
  const [indices, setIndices] = useState<MarketIndex[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/indices`)
        if (!res.ok) throw new Error('Failed to fetch')
        const data = await res.json()
        setIndices(data)
        setError(null)
      } catch (e) {
        setError('Không thể tải dữ liệu chỉ số')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
    // Refresh every 60 seconds
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <MarketIndexSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (error) {
    return <div className="text-red-500 text-sm">{error}</div>
  }

  return (
    <div className={className}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {indices.map((index) => (
          <StockIndexCard
            key={index.symbol}
            symbol={index.symbol}
            name={index.name}
            value={index.value}
            change={index.change}
            changePercent={index.change_percent}
            chartData={index.chart_data}
          />
        ))}
      </div>
    </div>
  )
}
```

### Step 4: Add Environment Variable
**File**: `apps/web/.env.local` (create if not exists)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Todo List
- [ ] Add `MarketIndex` interface
- [ ] Replace mock data with `useEffect` + fetch
- [ ] Add error state handling
- [ ] Add auto-refresh (60s interval)
- [ ] Add `NEXT_PUBLIC_API_URL` env var
- [ ] Test with running backend

## Success Criteria
- [ ] Dashboard shows real index data from API
- [ ] Loading skeleton appears during fetch
- [ ] Error message shown if API fails
- [ ] Data refreshes every 60 seconds
- [ ] Sparkline charts display correctly

## Risk Assessment
- **Medium**: CORS issues - ensure backend allows frontend origin
- **Low**: API latency - skeleton provides good UX

## Security Considerations
- API URL exposed to client (public data, acceptable)
- No sensitive data in this endpoint

## Next Steps
- Consider adding React Query for better caching
- Add WebSocket for real-time updates (future)
