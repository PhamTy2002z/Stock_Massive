# Phase 03: Frontend Integration

**Date:** 2025-12-20
**Priority:** High
**Status:** ✅ Complete
**Estimated Effort:** 2 hours
**Actual Effort:** ~2 hours
**Code Review:** plans/reports/code-reviewer-251220-1454-volume-anomaly-phase03.md

## Context

Integrate volume anomaly chart into stock detail page. Add React Query hook for data fetching and wire up to existing tab system.

**Design Decision:** Add as 4th tab "Volume Analysis" to maintain clean separation of concerns.

## Related Files

- `D:\Stock_Massive\apps\web\src\hooks\` (new hook file)
- `D:\Stock_Massive\apps\web\src\components\dashboard\stock-detail-tabs.tsx` (add 4th tab)
- `D:\Stock_Massive\apps\web\src\components\dashboard\stock-detail-client.tsx` (add tab content)
- `D:\Stock_Massive\apps\web\src\components\dashboard\index.ts` (exports)

## Implementation Steps

### Step 1: Create React Query Hook (30 min)

**File:** `D:\Stock_Massive\apps\web\src\hooks\use-volume-analysis.ts`

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchVolumeAnomalies, type VolumeAnomalyResponse } from "@/lib/api"

export function useVolumeAnalysis(symbol: string | null, days: number = 20) {
  return useQuery<VolumeAnomalyResponse>({
    queryKey: ["volume-analysis", symbol, days],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol is required")
      return fetchVolumeAnomalies(symbol, days)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  })
}
```

### Step 2: Add Volume Tab to Tabs Component (20 min)

**File:** `D:\Stock_Massive\apps\web\src\components\dashboard\stock-detail-tabs.tsx`

Update type definition:

```typescript
export type StockDetailTabValue = "overview" | "finance" | "shareholders" | "volume"
```

Add tab to `tabs` array:

```typescript
const tabs = [
  {
    value: "overview" as const,
    label: "Tổng Quan",
    icon: BarChart3,
  },
  {
    value: "finance" as const,
    label: "Tài Chính",
    icon: Wallet,
  },
  {
    value: "shareholders" as const,
    label: "Cổ Đông",
    icon: Users,
  },
  {
    value: "volume" as const,
    label: "Khối Lượng",
    icon: Activity, // Import from lucide-react
  },
]
```

Add import at top:

```typescript
import { BarChart3, Wallet, Users, Activity } from "lucide-react"
```

### Step 3: Create Volume Tab Content Component (40 min)

**File:** `D:\Stock_Massive\apps\web\src\components\dashboard\volume-tab-content.tsx`

```typescript
"use client"

import { useState } from "react"
import { useVolumeAnalysis } from "@/hooks/use-volume-analysis"
import { VolumeAnomalyChart, VolumeAnomalyChartSkeleton } from "./volume-anomaly-chart"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AlertCircle, RefreshCw } from "lucide-react"

interface VolumeTabContentProps {
  symbol: string
}

export function VolumeTabContent({ symbol }: VolumeTabContentProps) {
  const [days, setDays] = useState(20)
  const { data, isLoading, error, refetch, isFetching } = useVolumeAnalysis(symbol, days)

  if (error) {
    return (
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            Failed to Load Volume Data
          </CardTitle>
          <CardDescription>
            {error instanceof Error ? error.message : "An unexpected error occurred"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => refetch()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return <VolumeAnomalyChartSkeleton />
  }

  if (!data || data.time_slots.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No Volume Data Available</CardTitle>
          <CardDescription>
            Intraday volume data has not been collected for {symbol} yet.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Baseline Period:</span>
          <Select value={days.toString()} onValueChange={(v) => setDays(parseInt(v))}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10 days</SelectItem>
              <SelectItem value="20">20 days</SelectItem>
              <SelectItem value="30">30 days</SelectItem>
              <SelectItem value="60">60 days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button
          onClick={() => refetch()}
          variant="outline"
          size="sm"
          disabled={isFetching}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Chart */}
      <VolumeAnomalyChart
        data={data.time_slots}
        symbol={data.symbol}
        daysAnalyzed={data.days_analyzed}
        latestDate={data.latest_date}
      />

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">About Volume Anomaly Detection</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            This chart compares each 5-minute interval's volume against its {days}-day historical average
            to identify unusual trading activity.
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Elevated (1.5x-2x):</strong> Moderately higher than average</li>
            <li><strong>High (2x-3x):</strong> Significantly higher than average</li>
            <li><strong>Very High (&gt;3x):</strong> Exceptionally high volume spike</li>
          </ul>
          <p className="text-xs mt-3">
            Data source: Historical intraday bars collected daily. Latest data: {data.latest_date || "N/A"}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
```

### Step 4: Integrate into Stock Detail Client (20 min)

**File:** `D:\Stock_Massive\apps\web\src\components\dashboard\stock-detail-client.tsx`

Add import:

```typescript
import { VolumeTabContent } from "./volume-tab-content"
```

Add volume tab content after shareholders tab (around line 117):

```typescript
{activeTab === "finance" && <FinanceTabContent symbol={data.symbol} />}
{activeTab === "shareholders" && <ShareholdersTabContent symbol={data.symbol} />}
{activeTab === "volume" && <VolumeTabContent symbol={data.symbol} />}
```

### Step 5: Update Exports (5 min)

**File:** `D:\Stock_Massive\apps\web\src\components\dashboard\index.ts`

Add export:

```typescript
export { VolumeTabContent } from "./volume-tab-content"
```

**File:** `D:\Stock_Massive\apps\web\src\hooks\index.ts` (create if doesn't exist)

```typescript
export { useVolumeAnalysis } from "./use-volume-analysis"
```

### Step 6: Test Integration (25 min)

1. Start dev servers:
```bash
# Terminal 1 - Backend
cd D:\Stock_Massive\apps\api
uvicorn src.main:app --reload

# Terminal 2 - Frontend
cd D:\Stock_Massive\apps\web
pnpm dev
```

2. Navigate to stock detail page: `http://localhost:3000/dashboard?symbol=VCB`

3. Click "Khối Lượng" (Volume) tab

4. Verify:
   - Chart loads with 72 bars
   - Anomalies highlighted correctly
   - Baseline selector works (10/20/30/60 days)
   - Refresh button works
   - Tooltips show on hover
   - Loading skeleton displays during fetch
   - Error state shows if API fails

## Todo

- [x] Create use-volume-analysis.ts hook
- [x] Add "volume" to StockDetailTabValue type
- [x] Add Activity icon import to tabs component
- [x] Add volume tab to tabs array
- [x] Create volume-tab-content.tsx component
- [x] Add baseline period selector
- [x] Add refresh button
- [x] Add info card with explanation
- [x] Import VolumeTabContent in stock-detail-client.tsx
- [x] Add volume tab content rendering
- [x] Export VolumeTabContent from index.ts
- [x] Test tab switching
- [x] Test baseline period changes
- [x] Test error handling
- [x] Test with multiple symbols

## Success Criteria

- ✅ Volume tab appears as 4th tab in stock detail page
- ✅ Chart loads when tab is clicked
- ✅ Baseline period selector updates chart data
- ✅ Refresh button refetches data
- ✅ Loading skeleton shows during data fetch
- ✅ Error state displays with retry button
- ✅ Info card explains anomaly levels
- ✅ Tab switching preserves other tabs' state
- ✅ Component follows existing code patterns
- ✅ No console errors or warnings

## Review Summary

**Code Quality:** A-
**Security:** ✅ Clean (0 vulnerabilities)
**Performance:** ✅ Optimized (React Query caching, useMemo)
**Architecture:** ✅ YAGNI/KISS/DRY compliant
**Issues:** 0 critical, 0 high, 3 minor improvements suggested

See full review: plans/reports/code-reviewer-251220-1454-volume-anomaly-phase03.md

## Next Steps

1. ✅ Deploy to staging
2. ⚠️ Remove console.error from stock-search-bar.tsx (technical debt)
3. Consider: Wrap VolumeTabContent in React.memo for render optimization
4. Consider: Make StockDetailTabs fully controlled component
