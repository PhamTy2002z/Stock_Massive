# Phase 3: SSR Integration

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: [phase-02-hooks-migration.md](./phase-02-hooks-migration.md)
- **Next Phase**: [phase-04-cleanup-testing.md](./phase-04-cleanup-testing.md)

## Overview
- **Date**: 2024-12-19
- **Description**: Convert page.tsx to Server Component, add server-side prefetching, create client islands
- **Priority**: P1
- **Status**: pending
- **Effort**: 2h

## Requirements
1. Create server-side API fetch functions (lib/api-server.ts)
2. Convert page.tsx from "use client" to Server Component
3. Prefetch market indices and sector performance on server
4. Use HydrationBoundary to pass prefetched data to client
5. Extract interactive parts into client island components
6. Add Suspense boundaries for streaming
7. Maintain URL state management (symbol query param)
8. Preserve all existing UI/UX behavior

## Related Code Files
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx` - Main dashboard
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts` - Client API functions
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/` - Dashboard components

## Implementation Steps

### Step 1: Create Server-Side API Functions
Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api-server.ts`:

```typescript
import "server-only"
import type { MarketIndex, SectorPerformanceResponse, StockDetail } from "./api"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

async function fetchApiServer<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    next: { revalidate: 60 }, // ISR: revalidate every 60 seconds
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchMarketIndicesServer(): Promise<MarketIndex[]> {
  const data = await fetchApiServer<{ symbol: string; name: string; value: number; change: number; change_pct: number }[]>(
    "/stocks/market-indices"
  )

  return data.map((item) => ({
    symbol: item.symbol,
    name: item.name,
    value: item.value,
    change: item.change,
    changePercent: item.change_pct,
  }))
}

export async function fetchSectorPerformanceServer(): Promise<SectorPerformanceResponse> {
  return fetchApiServer<SectorPerformanceResponse>("/stocks/sector-performance")
}

export async function fetchStockDetailServer(symbol: string): Promise<StockDetail> {
  return fetchApiServer<StockDetail>(`/stocks/${encodeURIComponent(symbol)}/detail`)
}
```

### Step 2: Create Client Island for Stock Detail
Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/stock-detail-client.tsx`:

```typescript
"use client"

import { useState } from "react"
import { useStockDetail } from "@/hooks/use-stock-detail"
import {
  StockTickerHeader,
  StockDetailPanel,
  StockStatsTable,
  StockCompanyInfo,
  StockTickerHeaderSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
  StockDetailError,
  StockDetailEmpty,
  StockDetailTabs,
  StockDetailTabsSkeleton,
  FinanceTabContent,
  ShareholdersTabContent,
} from "@/components/dashboard"
import type { StockDetailTabValue } from "@/components/dashboard"

interface StockDetailClientProps {
  initialSymbol: string | null
}

export function StockDetailClient({ initialSymbol }: StockDetailClientProps) {
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>("overview")
  const { data, isLoading, error, refetch } = useStockDetail(initialSymbol)

  return (
    <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      {/* Left: Main Content */}
      <div className="space-y-4">
        {error && <StockDetailError error={error} onRetry={refetch} />}

        {isLoading && (
          <>
            <StockTickerHeaderSkeleton />
            <StockDetailTabsSkeleton className="mt-2" />
            <StockDetailPanelSkeleton />
            <StockStatsTableSkeleton />
          </>
        )}

        {!initialSymbol && !isLoading && !error && <StockDetailEmpty />}

        {!isLoading && !error && data && (
          <div className="stock-detail-enter">
            <StockTickerHeader
              symbol={data.symbol}
              companyName={data.company_name || data.symbol}
              price={data.price || 0}
              change={data.change || 0}
              changePercent={data.change_pct || 0}
            />
            <StockDetailTabs
              value={activeTab}
              onChange={setActiveTab}
              className="mt-2 mb-4"
            />

            {activeTab === "overview" && (
              <>
                <StockDetailPanel
                  volume={data.volume || 0}
                  exchange={data.exchange || "N/A"}
                  marketCap={data.market_cap || 0}
                  industry={data.industry || "N/A"}
                />
                <StockStatsTable
                  openPrice={data.open_price || data.ref_price || 0}
                  highPrice={data.high_price || 0}
                  lowPrice={data.low_price || 0}
                  tradingVolume={data.volume || 0}
                  marketCap={data.market_cap || 0}
                  high52Week={data.high_52_week || 0}
                  low52Week={data.low_52_week || 0}
                  avgVolume52Week={data.avg_volume_52_week || 0}
                  eps={data.eps}
                  pe={data.pe}
                  beta={data.beta}
                  dividendYield={data.dividend_yield}
                />
              </>
            )}

            {activeTab === "finance" && <FinanceTabContent symbol={data.symbol} />}
            {activeTab === "shareholders" && <ShareholdersTabContent symbol={data.symbol} />}
          </div>
        )}
      </div>

      {/* Right: Company Info Sidebar */}
      <div className="space-y-4">
        {isLoading && <StockCompanyInfoSkeleton />}
        {!isLoading && !error && data && (
          <StockCompanyInfo
            symbol={data.symbol}
            industry={data.industry || "N/A"}
            marketCap={data.market_cap || 0}
            outstandingShares={(data.outstanding_shares || 0) / 1_000_000_000}
            exchange={data.exchange}
            vn30Rank={null}
            description={data.description || "No description available."}
          />
        )}
      </div>
    </section>
  )
}
```

### Step 3: Create Client Island for Layout with Search
Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/dashboard-layout-client.tsx`:

```typescript
"use client"

import { useSearchParams, useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"

interface DashboardLayoutClientProps {
  children: React.ReactNode
}

export function DashboardLayoutClient({ children }: DashboardLayoutClientProps) {
  const searchParams = useSearchParams()
  const router = useRouter()

  const handleStockSelect = (symbol: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("symbol", symbol)
    router.push(`/?${params.toString()}`, { scroll: false })
  }

  return <DashboardLayout onStockSelect={handleStockSelect}>{children}</DashboardLayout>
}
```

### Step 4: Convert page.tsx to Server Component
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx`:

```typescript
import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  MarketIndices,
  SectorPerformance,
  FundCertificates,
  StockTickerHeaderSkeleton,
  StockDetailTabsSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
} from "@/components/dashboard"
import { StockDetailClient } from "@/components/dashboard/stock-detail-client"
import { fetchMarketIndicesServer, fetchSectorPerformanceServer, fetchStockDetailServer } from "@/lib/api-server"
import { queryKeys } from "@/lib/query-keys"

const DEFAULT_SYMBOL = "VCB"

interface HomeProps {
  searchParams: { symbol?: string }
}

async function prefetchData(symbol: string) {
  const queryClient = new QueryClient()

  // Prefetch market indices
  await queryClient.prefetchQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndicesServer,
  })

  // Prefetch sector performance
  await queryClient.prefetchQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformanceServer,
  })

  // Prefetch stock detail if symbol provided
  if (symbol) {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.stockDetail(symbol),
      queryFn: () => fetchStockDetailServer(symbol),
    })
  }

  return dehydrate(queryClient)
}

export default async function Home({ searchParams }: HomeProps) {
  const symbol = searchParams.symbol || DEFAULT_SYMBOL
  const dehydratedState = await prefetchData(symbol)

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense
        fallback={
          <DashboardLayoutClient>
            <div className="flex flex-col gap-6">
              <section>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Chỉ số thị trường
                </h2>
                <MarketIndices />
              </section>
              <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
                <div className="space-y-4">
                  <StockTickerHeaderSkeleton />
                  <StockDetailTabsSkeleton className="mt-2" />
                  <StockDetailPanelSkeleton />
                  <StockStatsTableSkeleton />
                </div>
                <div className="space-y-4">
                  <StockCompanyInfoSkeleton />
                </div>
              </section>
            </div>
          </DashboardLayoutClient>
        }
      >
        <DashboardLayoutClient>
          <div className="flex flex-col gap-6">
            {/* Market Indices Section */}
            <section>
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Chỉ số thị trường
              </h2>
              <MarketIndices />
            </section>

            {/* Selected Stock Detail */}
            <StockDetailClient initialSymbol={symbol} />

            {/* Sector Performance & Fund Certificates */}
            <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
              <div>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Hiệu suất ngành
                </h2>
                <SectorPerformance />
              </div>

              <div>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Chứng chỉ quỹ
                </h2>
                <FundCertificates />
              </div>
            </section>
          </div>
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}
```

### Step 5: Install server-only Package
```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/web
pnpm add server-only
```

### Step 6: Update MarketIndices Component
Ensure `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/market-indices.tsx` uses TanStack Query:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
// ... rest of component
```

### Step 7: Test SSR
```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/web
pnpm build
pnpm start
```

Verify:
- View page source: market indices data should be in HTML
- Network tab: initial data loads from server
- No hydration errors in console
- URL state works (/?symbol=VCB)

## Success Criteria
- [x] Server-side API functions created (api-server.ts)
- [x] page.tsx is Server Component (no "use client")
- [x] Market indices prefetched on server
- [x] Sector performance prefetched on server
- [x] Stock detail prefetched for initial symbol
- [x] HydrationBoundary passes data to client
- [x] Client islands handle interactivity
- [x] URL state management works
- [x] Suspense boundaries added
- [x] No hydration mismatches
- [x] View source shows prefetched data
- [x] All features work as before

## Risk Assessment

**High Risk**:
- Hydration mismatches between server/client
- URL state management breaking
- Client components not receiving prefetched data

**Mitigations**:
- Use HydrationBoundary correctly
- Test with pnpm build + pnpm start (not just dev)
- Keep client islands minimal
- Use Suspense for streaming
- Verify query keys match between server/client
- Add proper error boundaries
