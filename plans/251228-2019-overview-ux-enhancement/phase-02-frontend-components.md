# Phase 2: Frontend Components

## Context Links

- [Main Plan](./plan.md)
- [Phase 1: Backend API](./phase-01-backend-api.md)
- [Existing MarketIndices](../../../apps/web/src/components/dashboard/market-indices.tsx)
- [Collapsible Component](../../../apps/web/src/components/ui/collapsible.tsx)

## Overview

- **Priority:** P2
- **Status:** Pending
- **Effort:** 3h
- **Description:** Create 4 collapsible dashboard widgets and integrate with new API endpoint.

## Key Insights

1. **ShadCN Collapsible** - Already exists at `components/ui/collapsible.tsx`
2. **Pattern Reference** - Follow `MarketIndices` component structure
3. **localStorage** - Use for collapsed state persistence
4. **10s Auto-refresh** - Match existing pattern with useSuspenseQuery

## Requirements

### Functional
- Market Breadth widget with bar visualization
- Top Movers widget with side-by-side gainers/losers
- Foreign Flow widget with net buy/sell lists
- All sections collapsible with persist state

### Non-Functional
- Initial render < 100ms (after data load)
- Smooth collapse/expand animation
- Mobile responsive

## Architecture

```
page.tsx
├── MarketIndices (existing)
├── CollapsibleSection
│   └── MarketBreadth
├── CollapsibleSection (grid 2-col)
│   ├── TopMovers
│   └── ForeignFlow
├── VN30OverviewTable (existing)
├── SectorPerformance (existing)
└── FundCertificates (existing)
```

## Related Code Files

### Files to Create
| Path | Description |
|------|-------------|
| `apps/web/src/hooks/use-market-overview.ts` | TanStack Query hook |
| `apps/web/src/components/dashboard/market-breadth.tsx` | Breadth widget |
| `apps/web/src/components/dashboard/top-movers.tsx` | Gainers/losers widget |
| `apps/web/src/components/dashboard/foreign-flow.tsx` | Foreign flow widget |
| `apps/web/src/components/dashboard/collapsible-section.tsx` | Wrapper component |

### Files to Modify
| Path | Description |
|------|-------------|
| `apps/web/src/app/page.tsx` | Add new sections |
| `apps/web/src/lib/api.ts` | Add fetchMarketOverview |
| `apps/web/src/lib/query-keys.ts` | Add marketOverview key |
| `apps/web/src/components/dashboard/index.ts` | Export new components |

## Implementation Steps

### Step 1: Add API Function
```typescript
// apps/web/src/lib/api.ts - Add to existing file

export interface MarketBreadth {
  advances: number
  declines: number
  unchanged: number
  total: number
}

export interface TopMoverItem {
  symbol: string
  price: number
  change_pct: number
  volume?: number
}

export interface ForeignFlowItem {
  symbol: string
  net_value: number
}

export interface ForeignFlowData {
  net_buy: ForeignFlowItem[]
  net_sell: ForeignFlowItem[]
  total_net_value: number
}

export interface TopVolumeItem {
  symbol: string
  price: number
  volume: number
  value: number
}

export interface MarketOverviewResponse {
  market_breadth: MarketBreadth
  top_gainers: TopMoverItem[]
  top_losers: TopMoverItem[]
  foreign_flow: ForeignFlowData
  top_volume: TopVolumeItem[]
  generated_at: string
}

export async function fetchMarketOverview(): Promise<MarketOverviewResponse> {
  const response = await fetch(`${API_BASE}/market-overview`)
  if (!response.ok) throw new Error("Failed to fetch market overview")
  return response.json()
}
```

### Step 2: Add Query Key
```typescript
// apps/web/src/lib/query-keys.ts - Add to existing

export const queryKeys = {
  // ... existing keys
  marketOverview: ["market-overview"] as const,
}
```

### Step 3: Create Hook
```typescript
// apps/web/src/hooks/use-market-overview.ts

"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchMarketOverview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketOverview() {
  return useSuspenseQuery({
    queryKey: queryKeys.marketOverview,
    queryFn: fetchMarketOverview,
    refetchInterval: 10000, // 10s auto-refresh
    staleTime: 5000,
  })
}
```

### Step 4: Create CollapsibleSection Wrapper
```typescript
// apps/web/src/components/dashboard/collapsible-section.tsx

"use client"

import { useState, useEffect } from "react"
import { ChevronDown } from "lucide-react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"

interface CollapsibleSectionProps {
  id: string
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
  className?: string
}

export function CollapsibleSection({
  id,
  title,
  children,
  defaultOpen = true,
  className,
}: CollapsibleSectionProps) {
  const storageKey = `section-collapsed-${id}`

  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window === "undefined") return defaultOpen
    const stored = localStorage.getItem(storageKey)
    return stored !== null ? stored === "true" : defaultOpen
  })

  useEffect(() => {
    localStorage.setItem(storageKey, String(isOpen))
  }, [isOpen, storageKey])

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} className={className}>
      <CollapsibleTrigger className="flex items-center justify-between w-full py-2 group">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up">
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}
```

### Step 5: Create MarketBreadth Component
```typescript
// apps/web/src/components/dashboard/market-breadth.tsx

"use client"

import { useMarketOverview } from "@/hooks/use-market-overview"
import { Card, CardContent } from "@/components/ui/card"

export function MarketBreadth() {
  const { data } = useMarketOverview()
  const { advances, declines, unchanged, total } = data.market_breadth

  const advancesPct = total > 0 ? (advances / total) * 100 : 0
  const declinesPct = total > 0 ? (declines / total) * 100 : 0
  const unchangedPct = total > 0 ? (unchanged / total) * 100 : 0

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-center justify-between mb-3 text-sm">
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-green-500" />
            Tăng: {advances} ({advancesPct.toFixed(1)}%)
          </span>
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-500" />
            Giảm: {declines} ({declinesPct.toFixed(1)}%)
          </span>
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-gray-400" />
            Đứng giá: {unchanged}
          </span>
        </div>
        <div className="h-3 flex rounded-full overflow-hidden bg-muted">
          <div
            className="bg-green-500 transition-all"
            style={{ width: `${advancesPct}%` }}
          />
          <div
            className="bg-gray-400 transition-all"
            style={{ width: `${unchangedPct}%` }}
          />
          <div
            className="bg-red-500 transition-all"
            style={{ width: `${declinesPct}%` }}
          />
        </div>
      </CardContent>
    </Card>
  )
}
```

### Step 6: Create TopMovers Component
```typescript
// apps/web/src/components/dashboard/top-movers.tsx

"use client"

import { useMarketOverview } from "@/hooks/use-market-overview"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function TopMovers() {
  const { data } = useMarketOverview()

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Top Biến động</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Gainers */}
          <div>
            <h4 className="text-sm font-medium text-green-500 mb-2">🟢 Tăng mạnh</h4>
            <div className="space-y-1">
              {data.top_gainers.map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-green-500">+{item.change_pct.toFixed(2)}%</span>
                </div>
              ))}
            </div>
          </div>
          {/* Losers */}
          <div>
            <h4 className="text-sm font-medium text-red-500 mb-2">🔴 Giảm mạnh</h4>
            <div className="space-y-1">
              {data.top_losers.map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-red-500">{item.change_pct.toFixed(2)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

### Step 7: Create ForeignFlow Component
```typescript
// apps/web/src/components/dashboard/foreign-flow.tsx

"use client"

import { useMarketOverview } from "@/hooks/use-market-overview"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

function formatBillion(value: number): string {
  const billions = value / 1e9
  return `${billions >= 0 ? "+" : ""}${billions.toFixed(1)} tỷ`
}

export function ForeignFlow() {
  const { data } = useMarketOverview()
  const { net_buy, net_sell, total_net_value } = data.foreign_flow

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-base">Giao dịch NDNN</CardTitle>
          <span className={cn(
            "text-sm font-medium",
            total_net_value >= 0 ? "text-green-500" : "text-red-500"
          )}>
            Net: {formatBillion(total_net_value)}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Net Buy */}
          <div>
            <h4 className="text-sm font-medium text-green-500 mb-2">Mua ròng</h4>
            <div className="space-y-1">
              {net_buy.slice(0, 5).map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-green-500">{formatBillion(item.net_value)}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Net Sell */}
          <div>
            <h4 className="text-sm font-medium text-red-500 mb-2">Bán ròng</h4>
            <div className="space-y-1">
              {net_sell.slice(0, 5).map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-red-500">{formatBillion(Math.abs(item.net_value))}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

### Step 8: Export Components
```typescript
// apps/web/src/components/dashboard/index.ts - Add exports

export { CollapsibleSection } from "./collapsible-section"
export { MarketBreadth } from "./market-breadth"
export { TopMovers } from "./top-movers"
export { ForeignFlow } from "./foreign-flow"
```

## Todo List

- [ ] Add types and fetch function to `lib/api.ts`
- [ ] Add query key to `lib/query-keys.ts`
- [ ] Create `use-market-overview.ts` hook
- [ ] Create `collapsible-section.tsx` wrapper
- [ ] Create `market-breadth.tsx` component
- [ ] Create `top-movers.tsx` component
- [ ] Create `foreign-flow.tsx` component
- [ ] Export from `components/dashboard/index.ts`
- [ ] Test components in isolation

## Success Criteria

- [ ] All components render without errors
- [ ] Collapsible state persists in localStorage
- [ ] 10s auto-refresh works
- [ ] Mobile responsive
- [ ] Smooth animations

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| API not ready | Can't test | Mock data in hook |
| Hydration mismatch | Console error | useEffect for localStorage |
| Large re-renders | Performance | Memoize components |

## Security Considerations

- No user input in these components
- XSS safe (no dangerouslySetInnerHTML)

## Next Steps

After this phase:
1. Phase 3: Integrate into page.tsx
2. Add Suspense boundaries
3. Polish UI and add loading skeletons
