"use client"

import { useMemo, memo } from "react"
import { isEqual } from "lodash-es"
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { IndustryVolumeSpikeGroup, VolumeSpikeAnomalyLevel } from "@/lib/api"

interface VolumeSpikeComposedChartProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
  isPlaceholderData?: boolean
}

// Color mapping for anomaly levels
function getBarColor(anomalyLevel: VolumeSpikeAnomalyLevel): string {
  const colors: Record<VolumeSpikeAnomalyLevel, string> = {
    very_high: "hsl(0 84% 60%)",
    high: "hsl(25 95% 53%)",
    elevated: "hsl(45 93% 47%)",
    normal: "hsl(var(--muted-foreground))",
  }
  return colors[anomalyLevel] || colors.normal
}

// Custom tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{
    payload: {
      symbol: string
      spike_ratio: number
      price_change_pct: number
      anomaly_level: VolumeSpikeAnomalyLevel
    }
  }>
}) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.symbol}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Tỷ lệ KL:</span>
            <span className="font-medium">{data.spike_ratio.toFixed(1)}x</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Thay đổi giá:</span>
            <span className={data.price_change_pct >= 0 ? "text-green-500" : "text-red-500"}>
              {data.price_change_pct >= 0 ? "+" : ""}
              {data.price_change_pct.toFixed(2)}%
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export const VolumeSpikeComposedChart = memo(function VolumeSpikeComposedChart({
  industries,
  className,
  isPlaceholderData = false,
}: VolumeSpikeComposedChartProps) {
  const chartData = useMemo(() => {
    if (!industries?.length) return []
    return industries
      .flatMap((g) => g.stocks)
      .sort((a, b) => b.spike_ratio - a.spike_ratio)
      .slice(0, 20)
      .map((s) => ({
        symbol: s.symbol,
        spike_ratio: s.spike_ratio,
        price_change_pct: s.price_change_pct ?? 0,
        anomaly_level: s.anomaly_level,
      }))
  }, [industries])

  if (chartData.length === 0) return null

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Khối lượng vs Giá (Top 20)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart
            data={chartData}
            margin={{ top: 10, right: 30, left: 0, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="symbol"
              tick={{ fontSize: 10 }}
              angle={-45}
              textAnchor="end"
              height={60}
              className="text-muted-foreground"
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11 }}
              className="text-muted-foreground"
              label={{
                value: "Tỷ lệ KL",
                angle: -90,
                position: "insideLeft",
                fontSize: 11,
                fill: "hsl(var(--muted-foreground))",
              }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11 }}
              className="text-muted-foreground"
              label={{
                value: "% Giá",
                angle: 90,
                position: "insideRight",
                fontSize: 11,
                fill: "hsl(var(--muted-foreground))",
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar
              yAxisId="left"
              dataKey="spike_ratio"
              name="Tỷ lệ KL"
              maxBarSize={28}
              isAnimationActive={!isPlaceholderData}
              animationDuration={300}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.anomaly_level)} />
              ))}
            </Bar>
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="price_change_pct"
              name="% Giá"
              stroke="hsl(142 76% 36%)"
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={!isPlaceholderData}
              animationDuration={300}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}, (prevProps, nextProps) => {
  return isEqual(prevProps.industries, nextProps.industries) &&
    prevProps.isPlaceholderData === nextProps.isPlaceholderData
})

export function VolumeSpikeComposedChartSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="h-5 w-48 bg-muted animate-pulse rounded" />
      </CardHeader>
      <CardContent>
        <div className="h-[350px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
