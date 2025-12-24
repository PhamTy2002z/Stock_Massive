# Phase 02: Frontend Money Flow Tab

## Context

- **Plan**: [plan.md](./plan.md)
- **Depends on**: [phase-01](./phase-01-backend-trading-news-apis.md) (Backend APIs)
- **Docs**: [codebase-summary.md](../../docs/codebase-summary.md)

## Overview

| Field | Value |
|-------|-------|
| Priority | P1 |
| Status | Pending |
| Effort | 3h |
| Description | Create "Dòng Tiền" tab with Foreign + Prop trading charts |

## Key Insights

- Use Recharts BarChart (already in stack)
- Lazy load data on tab switch
- 30-day default range
- Combine foreign + prop trading in single tab
- Show summary stats above charts

## Requirements

**Functional:**
- Bar chart: Foreign net buy/sell by day (30D)
- Bar chart: Prop trading net volume by day (30D)
- Summary cards: Total net volume, ownership %, remaining room
- Loading skeleton on first load

**Non-functional:**
- Tab content loads < 1s (after API response)
- Responsive charts

## Architecture

```
apps/web/src/
├── components/dashboard/
│   ├── money-flow-tab-content.tsx      # NEW - Main container
│   ├── foreign-trading-chart.tsx       # NEW - Foreign chart
│   ├── prop-trading-chart.tsx          # NEW - Prop chart
│   ├── money-flow-summary-cards.tsx    # NEW - Summary stats
│   ├── money-flow-skeleton.tsx         # NEW - Loading state
│   └── index.ts                        # Export new components
├── hooks/
│   ├── use-foreign-trading.ts          # NEW
│   ├── use-prop-trading.ts             # NEW
│   └── index.ts
└── lib/
    ├── api.ts                          # Add API functions
    └── query-keys.ts                   # Add query keys
```

## Related Code Files

**Create:**
- `apps/web/src/components/dashboard/money-flow-tab-content.tsx`
- `apps/web/src/components/dashboard/foreign-trading-chart.tsx`
- `apps/web/src/components/dashboard/prop-trading-chart.tsx`
- `apps/web/src/components/dashboard/money-flow-summary-cards.tsx`
- `apps/web/src/components/dashboard/money-flow-skeleton.tsx`
- `apps/web/src/hooks/use-foreign-trading.ts`
- `apps/web/src/hooks/use-prop-trading.ts`

**Modify:**
- `apps/web/src/components/dashboard/stock-detail-tabs.tsx` - Add "money-flow" tab
- `apps/web/src/components/dashboard/stock-detail-client.tsx` - Render MoneyFlowTabContent
- `apps/web/src/components/dashboard/index.ts` - Export new components
- `apps/web/src/lib/api.ts` - Add fetchForeignTrading, fetchPropTrading
- `apps/web/src/lib/query-keys.ts` - Add foreignTrading, propTrading keys

## Implementation Steps

### Step 1: Add API Functions (15min)

```typescript
// apps/web/src/lib/api.ts - ADD:

export interface ForeignTradingItem {
  date: string;
  net_volume: number;
  net_value: number;
  buy_volume: number;
  sell_volume: number;
  remaining_room: number;
  ownership_pct: number;
}

export interface ForeignTradingResponse {
  symbol: string;
  items: ForeignTradingItem[];
  total_net_volume: number;
  total_net_value: number;
}

export interface PropTradingItem {
  date: string;
  buy_volume: number;
  sell_volume: number;
  net_volume: number;
  net_value: number;
}

export interface PropTradingResponse {
  symbol: string;
  items: PropTradingItem[];
  total_net_volume: number;
}

export async function fetchForeignTrading(symbol: string, days = 30): Promise<ForeignTradingResponse> {
  const res = await fetch(`${API_BASE_URL}/stocks/${symbol}/foreign-trading?days=${days}`);
  if (!res.ok) throw new Error(`Failed to fetch foreign trading: ${res.status}`);
  return res.json();
}

export async function fetchPropTrading(symbol: string, days = 30): Promise<PropTradingResponse> {
  const res = await fetch(`${API_BASE_URL}/stocks/${symbol}/prop-trading?days=${days}`);
  if (!res.ok) throw new Error(`Failed to fetch prop trading: ${res.status}`);
  return res.json();
}
```

### Step 2: Add Query Keys (5min)

```typescript
// apps/web/src/lib/query-keys.ts - ADD:
export const queryKeys = {
  // ... existing keys
  foreignTrading: (symbol: string, days = 30) => ['foreignTrading', symbol, days] as const,
  propTrading: (symbol: string, days = 30) => ['propTrading', symbol, days] as const,
}
```

### Step 3: Create Hooks (20min)

```typescript
// apps/web/src/hooks/use-foreign-trading.ts
import { useQuery } from "@tanstack/react-query";
import { fetchForeignTrading, ForeignTradingResponse } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useForeignTrading(symbol: string | null, days = 30) {
  return useQuery<ForeignTradingResponse>({
    queryKey: queryKeys.foreignTrading(symbol ?? "", days),
    queryFn: () => fetchForeignTrading(symbol!, days),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 min
  });
}
```

```typescript
// apps/web/src/hooks/use-prop-trading.ts
import { useQuery } from "@tanstack/react-query";
import { fetchPropTrading, PropTradingResponse } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function usePropTrading(symbol: string | null, days = 30) {
  return useQuery<PropTradingResponse>({
    queryKey: queryKeys.propTrading(symbol ?? "", days),
    queryFn: () => fetchPropTrading(symbol!, days),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}
```

### Step 4: Create Summary Cards Component (20min)

```typescript
// apps/web/src/components/dashboard/money-flow-summary-cards.tsx
"use client"

import { Card, CardContent } from "@/components/ui/card"
import { TrendingUp, TrendingDown, Users, Building2 } from "lucide-react"
import { formatNumber, formatPercent } from "@/lib/utils"

interface MoneyFlowSummaryCardsProps {
  foreignNetVolume: number;
  foreignOwnership: number;
  foreignRoom: number;
  propNetVolume: number;
}

export function MoneyFlowSummaryCards({
  foreignNetVolume,
  foreignOwnership,
  foreignRoom,
  propNetVolume,
}: MoneyFlowSummaryCardsProps) {
  const isForeignBuying = foreignNetVolume > 0;
  const isPropBuying = propNetVolume > 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Users className="h-4 w-4" />
            <span>Khối Ngoại Net</span>
          </div>
          <div className={`text-lg font-semibold ${isForeignBuying ? 'text-green-500' : 'text-red-500'}`}>
            {isForeignBuying ? '+' : ''}{formatNumber(foreignNetVolume)}
          </div>
        </CardContent>
      </Card>
      {/* Similar cards for ownership, room, prop net */}
    </div>
  );
}
```

### Step 5: Create Foreign Trading Chart (30min)

```typescript
// apps/web/src/components/dashboard/foreign-trading-chart.tsx
"use client"

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ForeignTradingItem } from "@/lib/api"

interface ForeignTradingChartProps {
  data: ForeignTradingItem[];
}

export function ForeignTradingChart({ data }: ForeignTradingChartProps) {
  const chartData = data.map(item => ({
    date: new Date(item.date).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' }),
    netVolume: item.net_volume / 1000, // Convert to thousands
    isPositive: item.net_volume >= 0,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Khối Ngoại - Net Volume (30D)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}K`} />
            <Tooltip formatter={(v: number) => [`${v.toFixed(0)}K`, 'Net Volume']} />
            <ReferenceLine y={0} stroke="#888" />
            <Bar dataKey="netVolume">
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry.isPositive ? '#22c55e' : '#ef4444'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

### Step 6: Create Prop Trading Chart (20min)

```typescript
// apps/web/src/components/dashboard/prop-trading-chart.tsx
// Similar structure to ForeignTradingChart
```

### Step 7: Create Money Flow Skeleton (10min)

```typescript
// apps/web/src/components/dashboard/money-flow-skeleton.tsx
"use client"

import { Skeleton } from "@/components/ui/skeleton"

export function MoneyFlowSkeleton() {
  return (
    <div className="space-y-4">
      {/* Summary cards skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
      {/* Charts skeleton */}
      <Skeleton className="h-[250px] rounded-lg" />
      <Skeleton className="h-[250px] rounded-lg" />
    </div>
  );
}
```

### Step 8: Create Tab Content Container (30min)

```typescript
// apps/web/src/components/dashboard/money-flow-tab-content.tsx
"use client"

import { useForeignTrading } from "@/hooks/use-foreign-trading"
import { usePropTrading } from "@/hooks/use-prop-trading"
import { MoneyFlowSummaryCards } from "./money-flow-summary-cards"
import { ForeignTradingChart } from "./foreign-trading-chart"
import { PropTradingChart } from "./prop-trading-chart"
import { MoneyFlowSkeleton } from "./money-flow-skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"

interface MoneyFlowTabContentProps {
  symbol: string;
}

export function MoneyFlowTabContent({ symbol }: MoneyFlowTabContentProps) {
  const { data: foreignData, isLoading: foreignLoading, error: foreignError } = useForeignTrading(symbol);
  const { data: propData, isLoading: propLoading, error: propError } = usePropTrading(symbol);

  const isLoading = foreignLoading || propLoading;
  const error = foreignError || propError;

  if (isLoading) return <MoneyFlowSkeleton />;

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>Failed to load money flow data</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <MoneyFlowSummaryCards
        foreignNetVolume={foreignData?.total_net_volume ?? 0}
        foreignOwnership={foreignData?.items[0]?.ownership_pct ?? 0}
        foreignRoom={foreignData?.items[0]?.remaining_room ?? 0}
        propNetVolume={propData?.total_net_volume ?? 0}
      />
      <ForeignTradingChart data={foreignData?.items ?? []} />
      <PropTradingChart data={propData?.items ?? []} />
    </div>
  );
}
```

### Step 9: Update Stock Detail Tabs (15min)

```typescript
// apps/web/src/components/dashboard/stock-detail-tabs.tsx - MODIFY:

export type StockDetailTabValue = "overview" | "finance" | "shareholders" | "volume" | "money-flow" | "news-events"

const tabs = [
  { value: "overview" as const, label: "Tổng Quan", icon: BarChart3 },
  { value: "finance" as const, label: "Tài Chính", icon: Wallet },
  { value: "shareholders" as const, label: "Cổ Đông", icon: Users },
  { value: "volume" as const, label: "Khối Lượng", icon: Activity },
  { value: "money-flow" as const, label: "Dòng Tiền", icon: TrendingUp },  // NEW
  { value: "news-events" as const, label: "Tin Tức", icon: Newspaper },   // NEW
]
```

### Step 10: Render Tab Content (15min)

```typescript
// apps/web/src/components/dashboard/stock-detail-client.tsx - ADD:
import { MoneyFlowTabContent } from "./money-flow-tab-content"

// In render:
{activeTab === "money-flow" && <MoneyFlowTabContent symbol={data.symbol} />}
```

### Step 11: Export Components (5min)

```typescript
// apps/web/src/components/dashboard/index.ts - ADD:
export * from "./money-flow-tab-content"
export * from "./foreign-trading-chart"
export * from "./prop-trading-chart"
export * from "./money-flow-summary-cards"
export * from "./money-flow-skeleton"
```

## Todo List

- [ ] Add ForeignTradingResponse, PropTradingResponse types to api.ts
- [ ] Add fetchForeignTrading, fetchPropTrading functions
- [ ] Add query keys for foreignTrading, propTrading
- [ ] Create use-foreign-trading.ts hook
- [ ] Create use-prop-trading.ts hook
- [ ] Create money-flow-summary-cards.tsx
- [ ] Create foreign-trading-chart.tsx with Recharts
- [ ] Create prop-trading-chart.tsx with Recharts
- [ ] Create money-flow-skeleton.tsx
- [ ] Create money-flow-tab-content.tsx container
- [ ] Add "money-flow" to StockDetailTabValue type
- [ ] Add tab definition to tabs array
- [ ] Render MoneyFlowTabContent in stock-detail-client
- [ ] Export all new components
- [ ] Test tab switching and data loading

## Success Criteria

- [ ] Money Flow tab appears in tabs bar
- [ ] Clicking tab loads data with skeleton
- [ ] Foreign chart shows 30-day bars (green/red)
- [ ] Prop chart shows 30-day bars
- [ ] Summary cards show correct totals
- [ ] Responsive on mobile
- [ ] Error state displays correctly

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Chart performance | Medium | Limit to 30 data points |
| Empty data | Low | Show "No data" message |

## Security Considerations

- No user input displayed raw
- API errors don't leak details

## Next Steps

→ Phase 03: Frontend News & Events Tab
