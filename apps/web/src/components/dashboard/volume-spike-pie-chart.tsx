"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"

interface VolumeSpikePieChartProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
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
function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

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

export function VolumeSpikePieChart({ industries, className }: VolumeSpikePieChartProps) {
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
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={topStocks}
              dataKey="spike_ratio"
              nameKey="symbol"
              cx="50%"
              cy="50%"
              outerRadius={90}
              innerRadius={40}
              label={renderCustomLabel}
              labelLine={false}
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
            <Legend
              verticalAlign="bottom"
              height={36}
              formatter={(value: string) => (
                <span className="text-xs text-muted-foreground">{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

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
