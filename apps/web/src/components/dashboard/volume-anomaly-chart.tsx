"use client"

import { useMemo } from "react"
import {
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  Cell,
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { VolumeTimeSlot, VolumeAnomalyLevel } from "@/lib/api"

interface VolumeAnomalyChartProps {
  data: VolumeTimeSlot[]
  symbol: string
  daysAnalyzed: number
  latestDate: string | null
  className?: string
}

// Color mapping for anomaly levels
const ANOMALY_COLORS: Record<VolumeAnomalyLevel, string> = {
  normal: "hsl(var(--muted-foreground))",
  elevated: "hsl(45 93% 47%)", // Yellow
  high: "hsl(25 95% 53%)", // Orange
  very_high: "hsl(0 84% 60%)", // Red
}

// Format volume with K/M suffixes
function formatVolume(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(0)}K`
  }
  return value.toString()
}

// Custom tooltip component
function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: VolumeTimeSlot }> }) {
  if (!active || !payload || !payload.length) return null

  const data = payload[0].payload
  const anomalyLabel = {
    normal: "Bình thường",
    elevated: "Tăng cao (1.5x-2x)",
    high: "Cao (2x-3x)",
    very_high: "Rất cao (>3x)",
  }[data.anomaly_level]

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.time_label}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Khối lượng:</span>
            <span className="font-medium">{formatVolume(data.current_volume)}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">TB ({data.sample_count}d):</span>
            <span className="font-medium">{formatVolume(data.avg_volume)}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Tỷ lệ:</span>
            <span className="font-medium">{data.volume_ratio}x</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Trạng thái:</span>
            <span
              className={cn(
                "font-medium",
                data.anomaly_level === "very_high" && "text-red-500",
                data.anomaly_level === "high" && "text-orange-500",
                data.anomaly_level === "elevated" && "text-yellow-500"
              )}
            >
              {anomalyLabel}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function VolumeAnomalyChart({
  data,
  symbol,
  daysAnalyzed,
  latestDate,
  className,
}: VolumeAnomalyChartProps) {
  // Calculate statistics
  const stats = useMemo(() => {
    const anomalies = data.filter((s) => s.anomaly_level !== "normal")
    return { anomalyCount: anomalies.length }
  }, [data])

  // X-axis tick formatter (show every 12th label = hourly)
  const xAxisTicks = useMemo(() => {
    return data.filter((_, i) => i % 12 === 0).map((s) => s.time_label)
  }, [data])

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Phát hiện bất thường khối lượng</span>
          <span className="text-sm font-normal text-muted-foreground">
            {symbol} • {latestDate || "N/A"}
          </span>
        </CardTitle>
        <CardDescription>
          Chu kỳ 5 phút • Baseline {daysAnalyzed} ngày • {stats.anomalyCount} bất thường
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="time_label"
              ticks={xAxisTicks}
              tick={{ fontSize: 11 }}
              className="text-muted-foreground"
              angle={-45}
              textAnchor="end"
              height={60}
            />
            <YAxis
              tickFormatter={formatVolume}
              tick={{ fontSize: 11 }}
              className="text-muted-foreground"
              width={50}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
            <Bar
              dataKey="current_volume"
              name="Khối lượng"
              radius={[2, 2, 0, 0]}
              maxBarSize={12}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={ANOMALY_COLORS[entry.anomaly_level]} />
              ))}
            </Bar>
            <Line
              type="monotone"
              dataKey="avg_volume"
              name="Trung bình"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Legend for anomaly colors */}
        <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-border/50">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-muted-foreground" />
            <span className="text-xs text-muted-foreground">Bình thường</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ANOMALY_COLORS.elevated }} />
            <span className="text-xs text-muted-foreground">Tăng cao (1.5x-2x)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ANOMALY_COLORS.high }} />
            <span className="text-xs text-muted-foreground">Cao (2x-3x)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ANOMALY_COLORS.very_high }} />
            <span className="text-xs text-muted-foreground">Rất cao (&gt;3x)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Loading skeleton
export function VolumeAnomalyChartSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <div className="h-6 w-48 bg-muted animate-pulse rounded" />
        <div className="h-4 w-64 bg-muted animate-pulse rounded mt-2" />
      </CardHeader>
      <CardContent>
        <div className="h-[400px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
