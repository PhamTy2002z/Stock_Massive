"use client"

import { useMemo } from "react"
import {
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Cell,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"

interface VolumeSpikeChartProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
}

// Color based on spike count intensity
function getBarColor(spikeCount: number, maxCount: number): string {
  const ratio = spikeCount / maxCount
  if (ratio > 0.7) return "hsl(0 84% 60%)" // Red
  if (ratio > 0.4) return "hsl(25 95% 53%)" // Orange
  return "hsl(45 93% 47%)" // Yellow
}

// Custom tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: { name: string; count: number; avgRatio: number } }>
}) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.name}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Số CP:</span>
            <span className="font-medium">{data.count}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Tỷ lệ TB:</span>
            <span className="font-medium">{data.avgRatio.toFixed(1)}x</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function VolumeSpikeChart({ industries, className }: VolumeSpikeChartProps) {
  const chartData = useMemo(() => {
    return industries
      .map((g) => ({
        name: g.icb_name.length > 20 ? g.icb_name.slice(0, 18) + "..." : g.icb_name,
        count: g.spike_count,
        avgRatio: g.avg_spike_ratio,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10) // Top 10 industries
  }, [industries])

  const maxCount = Math.max(...chartData.map((d) => d.count), 1)

  if (chartData.length === 0) {
    return null
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Phân bố theo ngành (Top 10)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} className="text-muted-foreground" />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11 }}
              className="text-muted-foreground"
              width={120}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
            <Bar dataKey="count" name="Số CP" radius={[0, 4, 4, 0]} maxBarSize={24}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.count, maxCount)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function VolumeSpikeChartSkeleton({ className }: { className?: string }) {
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
