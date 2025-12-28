# Phase 2: Health Scorecard UI

## Context

- **Plan**: [plan.md](../plan.md)
- **Phase 1**: [Backend APIs](phase-1-backend-apis.md) (prerequisite)
- **Research**: [researcher-01-recharts-financial-viz.md](../research/researcher-01-recharts-financial-viz.md)

## Overview

Create Financial Health Scorecard component with Radar chart visualization and score breakdown.

## Key Insights

- RadarChart from Recharts ideal for 5-dimension comparison
- Color coding: Green (>70), Yellow (50-70), Red (<50)
- F-Score (0-9) displayed as progress bar
- Mobile: Stack radar + details vertically

## Requirements

### Visual Design

```
┌─────────────────────────────────────────────────────────────┐
│  Financial Health Score                              VNM    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────┐  ┌───────────────────────────┐ │
│  │                         │  │ Overall Score             │ │
│  │     [RADAR CHART]       │  │    ████████░░  75/100     │ │
│  │                         │  │                           │ │
│  │  Profitability ●        │  │ F-Score: 7/9 (Strong)     │ │
│  │  Liquidity     ●        │  │ ████████░ 7/9             │ │
│  │  Leverage      ●        │  ├───────────────────────────┤ │
│  │  Efficiency    ●        │  │ Dimension Breakdown       │ │
│  │  Valuation     ●        │  │                           │ │
│  │                         │  │ Profitability  ████░ 85   │ │
│  └─────────────────────────┘  │ Liquidity      ███░░ 70   │ │
│                               │ Leverage       ████░ 80   │ │
│                               │ Efficiency     ██░░░ 65   │ │
│                               │ Valuation      ███░░ 75   │ │
│                               └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **HealthScoreCard** - Main container
2. **HealthRadarChart** - Recharts RadarChart
3. **ScoreBreakdown** - Dimension scores list
4. **FScoreIndicator** - F-Score progress bar

## Architecture

```
apps/web/src/components/dashboard/
├── financial-health/
│   ├── health-score-card.tsx        # Main container
│   ├── health-radar-chart.tsx       # Radar chart
│   ├── score-breakdown.tsx          # Dimension list
│   └── f-score-indicator.tsx        # F-Score bar
└── index.ts                          # Export
```

## Related Files

| File | Action |
|------|--------|
| `/apps/web/src/components/dashboard/financial-health/health-score-card.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-health/health-radar-chart.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-health/score-breakdown.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-health/f-score-indicator.tsx` | **NEW** |
| `/apps/web/src/hooks/use-health-score.ts` | **NEW** |
| `/apps/web/src/lib/api.ts` | Add `fetchHealthScore()` |

## Implementation Steps

### Step 1: Add API Client Function

**File: `/apps/web/src/lib/api.ts`**

```typescript
export interface HealthScoreDimension {
  score: number
  metrics: Record<string, number | null>
}

export interface FScoreDetails {
  positive_roa: boolean
  positive_cfo: boolean
  roa_improving: boolean
  accrual_quality: boolean
  leverage_decreasing: boolean
  liquidity_improving: boolean
}

export interface HealthScoreResponse {
  symbol: string
  health_score: number
  dimensions: Record<string, HealthScoreDimension>
  f_score: number
  f_score_details: FScoreDetails
}

export async function fetchHealthScore(symbol: string): Promise<HealthScoreResponse> {
  const response = await fetch(`${API_BASE_URL}/stocks/${symbol}/health-score`)
  if (!response.ok) throw new Error("Failed to fetch health score")
  return response.json()
}
```

### Step 2: Create TanStack Query Hook

**File: `/apps/web/src/hooks/use-health-score.ts`**

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchHealthScore, type HealthScoreResponse } from "@/lib/api"

export function useHealthScore(symbol: string | null) {
  return useQuery<HealthScoreResponse>({
    queryKey: ["health-score", symbol],
    queryFn: () => fetchHealthScore(symbol!),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
```

### Step 3: Create Radar Chart Component

**File: `/apps/web/src/components/dashboard/financial-health/health-radar-chart.tsx`**

```tsx
"use client"

import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Tooltip } from "recharts"
import type { HealthScoreDimension } from "@/lib/api"

interface HealthRadarChartProps {
  dimensions: Record<string, HealthScoreDimension>
}

const DIMENSION_LABELS: Record<string, string> = {
  profitability: "Sinh loi",
  liquidity: "Thanh khoan",
  leverage: "Don bay",
  efficiency: "Hieu qua",
  valuation: "Dinh gia",
}

export function HealthRadarChart({ dimensions }: HealthRadarChartProps) {
  const data = Object.entries(dimensions).map(([key, dim]) => ({
    dimension: DIMENSION_LABELS[key] || key,
    score: dim.score,
    fullMark: 100,
  }))

  return (
    <ResponsiveContainer width="100%" height={250}>
      <RadarChart data={data} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
        <PolarGrid strokeDasharray="3 3" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Radar
          name="Score"
          dataKey="score"
          stroke="hsl(var(--primary))"
          fill="hsl(var(--primary))"
          fillOpacity={0.3}
          strokeWidth={2}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number) => [`${value}/100`, "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
```

### Step 4: Create Score Breakdown Component

**File: `/apps/web/src/components/dashboard/financial-health/score-breakdown.tsx`**

```tsx
import { cn } from "@/lib/utils"
import type { HealthScoreDimension } from "@/lib/api"

interface ScoreBreakdownProps {
  dimensions: Record<string, HealthScoreDimension>
}

const DIMENSION_CONFIG: Record<string, { label: string; icon: string }> = {
  profitability: { label: "Sinh loi", icon: "TrendingUp" },
  liquidity: { label: "Thanh khoan", icon: "Droplets" },
  leverage: { label: "Don bay", icon: "Scale" },
  efficiency: { label: "Hieu qua", icon: "Gauge" },
  valuation: { label: "Dinh gia", icon: "Tag" },
}

function getScoreColor(score: number): string {
  if (score >= 70) return "text-green-500"
  if (score >= 50) return "text-yellow-500"
  return "text-red-500"
}

function getProgressColor(score: number): string {
  if (score >= 70) return "bg-green-500"
  if (score >= 50) return "bg-yellow-500"
  return "bg-red-500"
}

export function ScoreBreakdown({ dimensions }: ScoreBreakdownProps) {
  return (
    <div className="space-y-3">
      {Object.entries(dimensions).map(([key, dim]) => (
        <div key={key} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {DIMENSION_CONFIG[key]?.label || key}
            </span>
            <span className={cn("font-medium", getScoreColor(dim.score))}>
              {dim.score}
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", getProgressColor(dim.score))}
              style={{ width: `${dim.score}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
```

### Step 5: Create F-Score Indicator

**File: `/apps/web/src/components/dashboard/financial-health/f-score-indicator.tsx`**

```tsx
import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle } from "lucide-react"
import type { FScoreDetails } from "@/lib/api"

interface FScoreIndicatorProps {
  score: number
  details: FScoreDetails
}

const FSCORE_LABELS: Record<keyof FScoreDetails, string> = {
  positive_roa: "ROA duong",
  positive_cfo: "Dong tien duong",
  roa_improving: "ROA tang",
  accrual_quality: "Chat luong loi nhuan",
  leverage_decreasing: "Don bay giam",
  liquidity_improving: "Thanh khoan tang",
}

function getFScoreLabel(score: number): { text: string; color: string } {
  if (score >= 7) return { text: "Manh", color: "text-green-500" }
  if (score >= 4) return { text: "Trung binh", color: "text-yellow-500" }
  return { text: "Yeu", color: "text-red-500" }
}

export function FScoreIndicator({ score, details }: FScoreIndicatorProps) {
  const { text, color } = getFScoreLabel(score)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Piotroski F-Score</span>
        <span className={cn("font-bold", color)}>
          {score}/9 ({text})
        </span>
      </div>

      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            score >= 7 ? "bg-green-500" : score >= 4 ? "bg-yellow-500" : "bg-red-500"
          )}
          style={{ width: `${(score / 9) * 100}%` }}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        {Object.entries(details).map(([key, passed]) => (
          <div
            key={key}
            className={cn(
              "flex items-center gap-1",
              passed ? "text-green-500" : "text-muted-foreground"
            )}
          >
            {passed ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <XCircle className="h-3 w-3" />
            )}
            <span>{FSCORE_LABELS[key as keyof FScoreDetails]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

### Step 6: Create Main Container

**File: `/apps/web/src/components/dashboard/financial-health/health-score-card.tsx`**

```tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Activity } from "lucide-react"
import { useHealthScore } from "@/hooks/use-health-score"
import { HealthRadarChart } from "./health-radar-chart"
import { ScoreBreakdown } from "./score-breakdown"
import { FScoreIndicator } from "./f-score-indicator"
import { cn } from "@/lib/utils"

interface HealthScoreCardProps {
  symbol: string | null
  className?: string
}

export function HealthScoreCard({ symbol, className }: HealthScoreCardProps) {
  const { data, isLoading, error } = useHealthScore(symbol)

  if (!symbol) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[400px] text-muted-foreground">
          Chon mot co phieu de xem Health Score
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return <HealthScoreCardSkeleton className={className} />
  }

  if (error || !data) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[400px] text-destructive">
          Khong the tai Health Score
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Activity className="h-5 w-5" />
          Financial Health Score
          <span className="ml-auto text-primary font-bold">{data.symbol}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid md:grid-cols-2 gap-6">
          {/* Radar Chart */}
          <div>
            <HealthRadarChart dimensions={data.dimensions} />
          </div>

          {/* Score Details */}
          <div className="space-y-6">
            {/* Overall Score */}
            <div className="text-center p-4 bg-muted/30 rounded-lg">
              <div className="text-sm text-muted-foreground">Overall Score</div>
              <div className={cn(
                "text-4xl font-bold",
                data.health_score >= 70 ? "text-green-500" :
                data.health_score >= 50 ? "text-yellow-500" : "text-red-500"
              )}>
                {data.health_score}
                <span className="text-lg text-muted-foreground">/100</span>
              </div>
            </div>

            {/* F-Score */}
            <FScoreIndicator score={data.f_score} details={data.f_score_details} />

            {/* Dimension Breakdown */}
            <div>
              <h4 className="text-sm font-medium mb-3">Dimension Breakdown</h4>
              <ScoreBreakdown dimensions={data.dimensions} />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function HealthScoreCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent>
        <div className="grid md:grid-cols-2 gap-6">
          <Skeleton className="h-[250px]" />
          <div className="space-y-4">
            <Skeleton className="h-20" />
            <Skeleton className="h-16" />
            <Skeleton className="h-32" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

### Step 7: Export Components

**File: `/apps/web/src/components/dashboard/index.ts`**

```typescript
// Add exports
export * from "./financial-health/health-score-card"
export * from "./financial-health/health-radar-chart"
export * from "./financial-health/score-breakdown"
export * from "./financial-health/f-score-indicator"
```

## Todo

- [ ] Add API client function `fetchHealthScore()`
- [ ] Create `useHealthScore` hook
- [ ] Create `HealthRadarChart` component
- [ ] Create `ScoreBreakdown` component
- [ ] Create `FScoreIndicator` component
- [ ] Create `HealthScoreCard` container
- [ ] Add skeleton loading state
- [ ] Add error handling
- [ ] Export from index.ts

## Success Criteria

- [ ] Radar chart renders 5 dimensions correctly
- [ ] Score colors: Green (>70), Yellow (50-70), Red (<50)
- [ ] F-Score shows 6 criteria with pass/fail icons
- [ ] Responsive: stacks vertically on mobile
- [ ] Loading skeleton displays while fetching
- [ ] Error state handles API failures

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Recharts SSR issues | Low | Medium | "use client" directive |
| Missing data fields | Medium | Low | Show "N/A" for null values |
| Chart performance | Low | Low | Disable animations for refresh |
