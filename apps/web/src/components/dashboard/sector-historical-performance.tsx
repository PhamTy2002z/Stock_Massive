"use client"

import { useState, useMemo, memo, useEffect, useCallback, useRef } from "react"
import { isEqual } from "lodash-es"
import { RefreshCw } from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"
import {
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Cell,
  ReferenceLine,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { useSectorHistoricalPerformance } from "@/hooks/use-sector-historical-performance"
import { fetchSectorHistoricalPerformance, type SectorHistoricalPeriod } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

const PERIODS: SectorHistoricalPeriod[] = ["1W", "2W", "1M"]
const STALE_TIME = 5 * 60 * 1000 // 5 minutes - match hook staleTime

// Prefetch adjacent periods on mount for instant tab switching
function usePrefetchAdjacentPeriods(currentPeriod: SectorHistoricalPeriod) {
  const queryClient = useQueryClient()

  useEffect(() => {
    const currentIndex = PERIODS.indexOf(currentPeriod)
    const adjacentPeriods = [
      PERIODS[currentIndex - 1],
      PERIODS[currentIndex + 1],
    ].filter(Boolean) as SectorHistoricalPeriod[]

    adjacentPeriods.forEach((period) => {
      queryClient.prefetchQuery({
        queryKey: queryKeys.sectorHistoricalPerformance(period),
        queryFn: () => fetchSectorHistoricalPerformance(period),
        staleTime: STALE_TIME,
      })
    })
  }, [currentPeriod, queryClient])
}

// Custom tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: { name: string; value: number; isGainer: boolean } }>
}) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border">
      <CardContent className="p-3 space-y-1">
        <p className="font-semibold text-sm">{data.name}</p>
        <div className="flex justify-between gap-4 text-xs">
          <span className="text-muted-foreground">Thay đổi:</span>
          <span
            className={cn(
              "font-medium",
              data.value >= 0 ? "text-positive" : "text-negative"
            )}
          >
            {data.value >= 0 ? "+" : ""}
            {data.value.toFixed(2)}%
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

interface ChartProps {
  data: { name: string; value: number; isGainer: boolean }[]
  isPlaceholderData?: boolean
}

const SectorHistoricalChart = memo(
  function SectorHistoricalChart({ data, isPlaceholderData = false }: ChartProps) {
    if (data.length === 0) {
      return (
        <div className="h-[280px] flex items-center justify-center text-muted-foreground">
          Chưa có dữ liệu
        </div>
      )
    }

    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
            width={130}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
          <ReferenceLine x={0} stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
          <Bar
            dataKey="value"
            radius={[0, 4, 4, 0]}
            maxBarSize={20}
            isAnimationActive={!isPlaceholderData}
            animationDuration={300}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.isGainer ? "hsl(142 71% 45%)" : "hsl(0 84% 60%)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  },
  (prev, next) => isEqual(prev.data, next.data) && prev.isPlaceholderData === next.isPlaceholderData
)

function PeriodContent({ period }: { period: SectorHistoricalPeriod }) {
  const { data, error, isPending, isFetching, isPlaceholderData } =
    useSectorHistoricalPerformance(period)

  // useMemo must be called before any early returns (React hooks rules)
  const chartData = useMemo(() => {
    if (!data) return []
    const gainers = data.top_gainers.map((item) => ({
      name: item.icb_name.length > 18 ? item.icb_name.slice(0, 16) + "..." : item.icb_name,
      value: item.change_pct,
      isGainer: true,
    }))
    const losers = data.top_losers.map((item) => ({
      name: item.icb_name.length > 18 ? item.icb_name.slice(0, 16) + "..." : item.icb_name,
      value: item.change_pct,
      isGainer: false,
    }))
    return [...gainers, ...losers].sort((a, b) => b.value - a.value)
  }, [data])

  // First load only - show skeleton
  if (isPending) {
    return <div className="h-[280px] bg-muted animate-pulse rounded" />
  }

  // The API says *why* it has nothing (job not run yet, provider down). Show
  // that here rather than letting it take down the whole homepage.
  if (error) {
    return (
      <div className="flex h-[280px] flex-col items-center justify-center gap-2 px-6 text-center">
        <p className="text-sm font-medium text-foreground">
          Chưa có dữ liệu hiệu suất ngành
        </p>
        <p className="max-w-md text-sm text-muted-foreground">{error.message}</p>
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Chart stays visible during tab switch with opacity fade */}
      <div className={cn(
        "transition-opacity duration-200",
        isPlaceholderData && "opacity-60"
      )}>
        <SectorHistoricalChart data={chartData} isPlaceholderData={isPlaceholderData} />
      </div>

      {/* Subtle loading indicator during refetch */}
      {isFetching && !isPending && (
        <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm rounded-full p-1.5">
          <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  )
}

export function SectorHistoricalPerformance({ className }: { className?: string }) {
  const [period, setPeriod] = useState<SectorHistoricalPeriod>("1W")
  const queryClient = useQueryClient()
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Prefetch adjacent periods on mount/period change
  usePrefetchAdjacentPeriods(period)

  // Hover-based prefetch with 200ms delay (indicates user intent)
  const prefetchPeriod = useCallback((targetPeriod: SectorHistoricalPeriod) => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
    }
    hoverTimeoutRef.current = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: queryKeys.sectorHistoricalPerformance(targetPeriod),
        queryFn: () => fetchSectorHistoricalPerformance(targetPeriod),
        staleTime: STALE_TIME,
      })
    }, 200)
  }, [queryClient])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current)
      }
    }
  }, [])

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Hiệu suất ngành theo thời gian</CardTitle>
          <Tabs value={period} onValueChange={(v) => setPeriod(v as SectorHistoricalPeriod)}>
            <TabsList className="h-8">
              <TabsTrigger
                value="1W"
                className="text-xs px-3"
                onMouseEnter={() => prefetchPeriod("1W")}
              >
                1 Tuần
              </TabsTrigger>
              <TabsTrigger
                value="2W"
                className="text-xs px-3"
                onMouseEnter={() => prefetchPeriod("2W")}
              >
                2 Tuần
              </TabsTrigger>
              <TabsTrigger
                value="1M"
                className="text-xs px-3"
                onMouseEnter={() => prefetchPeriod("1M")}
              >
                1 Tháng
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </CardHeader>
      <CardContent>
        <PeriodContent period={period} />
      </CardContent>
    </Card>
  )
}

export function SectorHistoricalPerformanceSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="h-5 w-48 bg-muted animate-pulse rounded" />
          <div className="h-8 w-36 bg-muted animate-pulse rounded" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[280px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
