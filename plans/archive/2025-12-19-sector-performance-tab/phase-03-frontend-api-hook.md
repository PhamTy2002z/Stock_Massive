# Phase 3: Frontend API & Hook

## Context

Third phase of Sector Performance Tab feature. Add API client function and React hook with 5-minute auto-refresh.

## Overview

Create TypeScript types, fetch function in `api.ts`, and custom hook `use-sector-performance.ts` following existing patterns.

## Requirements

1. Define TypeScript interfaces matching backend schemas
2. Add `fetchSectorPerformance()` to api.ts
3. Create `use-sector-performance.ts` hook with:
   - Loading/error/data states
   - 5-minute auto-refresh interval
   - Manual refetch capability

## Architecture

```
use-sector-performance.ts
    ↓
fetchSectorPerformance() [api.ts]
    ↓
GET /api/v1/stocks/sector-performance
    ↓
SectorPerformanceResponse
```

## Related Files

| File | Action |
|------|--------|
| `apps/web/src/lib/api.ts` | Add types and fetch function |
| `apps/web/src/hooks/use-sector-performance.ts` | Create new hook |

## Implementation Steps

### Step 1: Add Types to `api.ts`

```typescript
// Sector Performance Types
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

### Step 2: Add Fetch Function to `api.ts`

```typescript
export async function fetchSectorPerformance(): Promise<SectorPerformanceResponse> {
  return fetchApi<SectorPerformanceResponse>("/stocks/sector-performance")
}
```

### Step 3: Create `use-sector-performance.ts`

```typescript
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { fetchSectorPerformance, SectorPerformanceResponse } from "@/lib/api"

const REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const [data, setData] = useState<SectorPerformanceResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const isMountedRef = useRef(true)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchSectorPerformance()
      if (isMountedRef.current) {
        setData(result)
        setLastUpdated(new Date())
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error("Failed to fetch sector performance"))
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true

    // Initial fetch
    fetchData()

    // Set up auto-refresh
    intervalRef.current = setInterval(fetchData, REFRESH_INTERVAL)

    return () => {
      isMountedRef.current = false
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetchData])

  const refetch = useCallback(() => {
    fetchData()
  }, [fetchData])

  return { data, isLoading, error, refetch, lastUpdated }
}
```

## Todo List

- [x] Add `SectorPerformanceItem` interface to api.ts
- [x] Add `SectorPerformanceResponse` interface to api.ts
- [x] Add `fetchSectorPerformance()` function to api.ts
- [x] Create `use-sector-performance.ts` hook file
- [x] Test hook in browser dev tools

## Success Criteria

- [x] Types match backend schema exactly
- [x] Fetch function returns typed response
- [x] Hook provides loading/error/data states
- [x] Auto-refresh triggers every 5 minutes
- [x] Manual refetch works correctly
- [x] Cleanup on unmount (no memory leaks)

## Risks

| Risk | Mitigation |
|------|------------|
| Memory leak on unmount | Use isMountedRef pattern |
| Stale interval | Clear on cleanup |
| Type mismatch | Match backend schema exactly |

## Testing

```typescript
// In browser console or component
const { data, isLoading, error, refetch, lastUpdated } = useSectorPerformance()

// Verify:
// 1. isLoading starts true
// 2. data populated after fetch
// 3. lastUpdated shows timestamp
// 4. refetch() triggers new fetch
// 5. Auto-refresh after 5 min
```

## Notes

- Pattern follows existing `use-stock-detail.ts` hook
- 5-min interval chosen to balance freshness vs API load
- `lastUpdated` useful for UI "Last updated: X" display
