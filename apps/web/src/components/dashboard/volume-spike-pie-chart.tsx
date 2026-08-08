"use client"

import { useMemo, memo } from "react"
import { useRouter } from "next/navigation"
import { isEqual } from "lodash-es"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { formatPercent } from "@/lib/format"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"

interface VolumeSpikePieChartProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
  isPlaceholderData?: boolean
}

// Distinct color palette for pie chart slices (10 colors)
const PIE_COLORS = [
  "hsl(0 84% 60%)",    // Red
  "hsl(25 95% 53%)",   // Orange
  "hsl(45 93% 47%)",   // Yellow
  "hsl(142 71% 45%)",  // Green
  "hsl(199 89% 48%)",  // Blue
  "hsl(262 83% 58%)",  // Purple
  "hsl(330 81% 60%)",  // Pink
  "hsl(174 72% 40%)",  // Teal
  "hsl(38 92% 50%)",   // Amber
  "hsl(221 83% 53%)",  // Indigo
]

// Get color by index for visual distinction
function getPieColor(index: number): string {
  return PIE_COLORS[index % PIE_COLORS.length]
}

// Format helpers
// Custom tooltip component
interface TooltipPayload {
  symbol: string
  spike_ratio: number
  price_change_pct: number | null
  company_name: string | null
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: TooltipPayload }>
}) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.symbol}</p>
        <p className="text-xs text-muted-foreground truncate max-w-[200px]">
          {data.company_name || "-"}
        </p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Tỷ lệ:</span>
            <span className="font-medium">{data.spike_ratio.toFixed(1)}x</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Giá:</span>
            <span className={data.price_change_pct !== null && data.price_change_pct >= 0 ? "text-green-500" : "text-red-500"}>
              {formatPercent(data.price_change_pct)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Custom label renderer for pie slices
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderCustomLabel(props: any) {
  const { cx, cy, midAngle, innerRadius, outerRadius, payload } = props
  if (typeof cx !== "number" || typeof cy !== "number" || typeof midAngle !== "number") {
    return null
  }
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      className="text-[10px] font-medium"
    >
      {payload?.symbol}
    </text>
  )
}

export const VolumeSpikePieChart = memo(function VolumeSpikePieChart({
  industries,
  className,
  isPlaceholderData = false,
}: VolumeSpikePieChartProps) {
  const router = useRouter()

  // Flatten all stocks, sort by spike_ratio, take top 10
  const topStocks = useMemo(() => {
    return industries
      .flatMap((g) => g.stocks)
      .sort((a, b) => b.spike_ratio - a.spike_ratio)
      .slice(0, 10)
      .map((s) => ({
        symbol: s.symbol,
        spike_ratio: s.spike_ratio,
        price_change_pct: s.price_change_pct,
        anomaly_level: s.anomaly_level,
        company_name: s.company_name,
      }))
  }, [industries])

  const handleSliceClick = (symbol: string) => {
    router.push(`/analytics/deep-dive?symbol=${encodeURIComponent(symbol)}`)
  }

  if (topStocks.length === 0) {
    return null
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Top 10 CP đột biến mạnh nhất</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col lg:flex-row items-center gap-6">
          {/* Pie Chart - larger, takes more space */}
          <div className="w-full lg:w-3/5 h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={topStocks}
                  dataKey="spike_ratio"
                  nameKey="symbol"
                  cx="50%"
                  cy="50%"
                  outerRadius={115}
                  innerRadius={50}
                  label={renderCustomLabel}
                  labelLine={false}
                  isAnimationActive={!isPlaceholderData}
                  animationDuration={300}
                >
                  {topStocks.map((stock, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={getPieColor(index)}
                      onClick={() => handleSliceClick(stock.symbol)}
                      className="cursor-pointer hover:opacity-80 transition-opacity outline-none focus:opacity-80"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === "Enter" && handleSliceClick(stock.symbol)}
                      aria-label={`${stock.symbol}: ${stock.spike_ratio.toFixed(1)}x`}
                    />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend as compact list - right side */}
          <div className="w-full lg:w-2/5 space-y-1">
            {topStocks.map((stock, index) => (
              <button
                key={stock.symbol}
                onClick={() => handleSliceClick(stock.symbol)}
                className="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-muted/50 transition-colors text-left"
              >
                <span
                  className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: getPieColor(index) }}
                />
                <span className="text-sm font-medium w-12 flex-shrink-0">{stock.symbol}</span>
                <span className="text-xs text-muted-foreground truncate flex-1 min-w-0">
                  {stock.company_name || "-"}
                </span>
                <span className="text-xs text-muted-foreground flex-shrink-0">{stock.spike_ratio.toFixed(1)}x</span>
                <span className={cn(
                  "text-xs w-14 text-right flex-shrink-0",
                  stock.price_change_pct !== null && stock.price_change_pct >= 0
                    ? "text-green-500"
                    : "text-red-500"
                )}>
                  {formatPercent(stock.price_change_pct)}
                </span>
              </button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}, (prevProps, nextProps) => {
  return isEqual(prevProps.industries, nextProps.industries) &&
    prevProps.isPlaceholderData === nextProps.isPlaceholderData
})

export function VolumeSpikePieChartSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="h-5 w-48 bg-muted animate-pulse rounded" />
      </CardHeader>
      <CardContent>
        <div className="h-[300px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
