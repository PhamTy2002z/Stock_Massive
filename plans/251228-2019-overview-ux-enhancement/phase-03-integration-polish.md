# Phase 3: Integration & Polish

## Context Links

- [Main Plan](./plan.md)
- [Phase 1: Backend API](./phase-01-backend-api.md)
- [Phase 2: Frontend Components](./phase-02-frontend-components.md)
- [Current page.tsx](../../../apps/web/src/app/page.tsx)

## Overview

- **Priority:** P2
- **Status:** Pending
- **Effort:** 2h
- **Description:** Integrate new widgets into Overview page, add loading states, and polish UI.

## Key Insights

1. **Suspense Pattern** - Use ErrorBoundary + Suspense for each section
2. **Prefetch** - Add marketOverview to prefetchData function
3. **Grid Layout** - 2-column grid for TopMovers + ForeignFlow
4. **Loading Skeletons** - Match existing skeleton patterns

## Requirements

### Functional
- New widgets appear between MarketIndices and VN30OverviewTable
- Collapsed state persists across page navigations
- Loading skeletons during data fetch

### Non-Functional
- No layout shift on load
- Smooth transitions

## Related Code Files

### Files to Modify
| Path | Description |
|------|-------------|
| `apps/web/src/app/page.tsx` | Add new sections |
| `apps/web/src/lib/api-server.ts` | Add server prefetch |

### Files to Create
| Path | Description |
|------|-------------|
| `apps/web/src/components/dashboard/market-overview-skeleton.tsx` | Loading skeleton |

## Implementation Steps

### Step 1: Add Server Prefetch
```typescript
// apps/web/src/lib/api-server.ts - Add to existing

export async function fetchMarketOverviewServer(): Promise<MarketOverviewResponse> {
  const response = await fetch(`${API_BASE_SERVER}/market-overview`, {
    next: { revalidate: 10 }, // ISR 10s
  })
  if (!response.ok) throw new Error("Failed to fetch market overview")
  return response.json()
}
```

### Step 2: Create Loading Skeleton
```typescript
// apps/web/src/components/dashboard/market-overview-skeleton.tsx

import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function MarketBreadthSkeleton() {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex justify-between mb-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-24" />
        </div>
        <Skeleton className="h-3 w-full rounded-full" />
      </CardContent>
    </Card>
  )
}

export function TopMoversSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <Skeleton className="h-5 w-24" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {[0, 1].map((col) => (
            <div key={col} className="space-y-2">
              <Skeleton className="h-4 w-20" />
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export function ForeignFlowSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between">
          <Skeleton className="h-5 w-28" />
          <Skeleton className="h-4 w-20" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {[0, 1].map((col) => (
            <div key={col} className="space-y-2">
              <Skeleton className="h-4 w-16" />
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export function MarketOverviewSkeleton() {
  return (
    <>
      <MarketBreadthSkeleton />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TopMoversSkeleton />
        <ForeignFlowSkeleton />
      </div>
    </>
  )
}
```

### Step 3: Update page.tsx
```typescript
// apps/web/src/app/page.tsx - Replace entire file

import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  MarketIndices,
  SectorPerformanceSection,
  FundCertificates,
  VN30OverviewTable,
  CollapsibleSection,
  MarketBreadth,
  TopMovers,
  ForeignFlow,
} from "@/components/dashboard"
import {
  MarketBreadthSkeleton,
  TopMoversSkeleton,
  ForeignFlowSkeleton,
} from "@/components/dashboard/market-overview-skeleton"
import {
  fetchMarketIndicesServer,
  fetchSectorPerformanceServer,
  fetchMarketOverviewServer,
} from "@/lib/api-server"
import { queryKeys } from "@/lib/query-keys"

async function prefetchData() {
  const queryClient = new QueryClient()

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: queryKeys.marketIndices,
      queryFn: fetchMarketIndicesServer,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.sectorPerformance,
      queryFn: fetchSectorPerformanceServer,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.marketOverview,
      queryFn: fetchMarketOverviewServer,
    }),
  ])

  return dehydrate(queryClient)
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-4">
          Chỉ số thị trường
        </h2>
        <MarketIndices />
      </section>
    </div>
  )
}

export default async function Home() {
  const dehydratedState = await prefetchData()

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense fallback={<DashboardLayoutClient><DashboardSkeleton /></DashboardLayoutClient>}>
        <DashboardLayoutClient>
          <div className="flex flex-col gap-6">
            {/* Market Indices Section */}
            <section>
              <MarketIndices />
            </section>

            {/* NEW: Market Breadth Section */}
            <CollapsibleSection id="market-breadth" title="Độ rộng thị trường">
              <Suspense fallback={<MarketBreadthSkeleton />}>
                <MarketBreadth />
              </Suspense>
            </CollapsibleSection>

            {/* NEW: Top Movers + Foreign Flow Grid */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <CollapsibleSection id="top-movers" title="Top Biến động">
                <Suspense fallback={<TopMoversSkeleton />}>
                  <TopMovers />
                </Suspense>
              </CollapsibleSection>

              <CollapsibleSection id="foreign-flow" title="Giao dịch NDNN">
                <Suspense fallback={<ForeignFlowSkeleton />}>
                  <ForeignFlow />
                </Suspense>
              </CollapsibleSection>
            </section>

            {/* VN30 Overview Section */}
            <section>
              <VN30OverviewTable />
            </section>

            {/* Sector Performance & Fund Certificates */}
            <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
              <SectorPerformanceSection />
              <FundCertificates />
            </section>
          </div>
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}
```

### Step 4: Export Skeleton Components
```typescript
// apps/web/src/components/dashboard/index.ts - Add exports

export {
  MarketBreadthSkeleton,
  TopMoversSkeleton,
  ForeignFlowSkeleton,
  MarketOverviewSkeleton,
} from "./market-overview-skeleton"
```

## Todo List

- [ ] Add `fetchMarketOverviewServer` to `api-server.ts`
- [ ] Create `market-overview-skeleton.tsx`
- [ ] Update `page.tsx` with new layout
- [ ] Export skeleton components
- [ ] Test full page load
- [ ] Test collapsed state persistence
- [ ] Test auto-refresh behavior
- [ ] Manual testing on mobile
- [ ] Performance check (Lighthouse)

## Success Criteria

- [ ] All widgets render correctly on page load
- [ ] Collapsed state persists after refresh
- [ ] Loading skeletons appear during fetch
- [ ] No layout shift
- [ ] Mobile responsive (stacked layout)
- [ ] 10s auto-refresh works for all widgets

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSR hydration error | Page crash | Test thoroughly |
| Too many Suspense boundaries | Waterfall loading | Prefetch all in parallel |
| localStorage SSR | Hydration mismatch | useEffect guard |

## Security Considerations

- No additional security concerns
- All data is public market information

## Next Steps

After this phase:
1. Write unit tests for components
2. Write E2E tests for full flow
3. Monitor performance in production
4. Gather user feedback
