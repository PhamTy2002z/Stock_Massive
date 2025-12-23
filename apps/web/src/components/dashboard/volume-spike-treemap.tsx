"use client"

import { useMemo, memo } from "react"
import { Treemap, ResponsiveContainer, Tooltip } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { IndustryVolumeSpikeGroup, VolumeSpikeAnomalyLevel } from "@/lib/api"

interface VolumeSpikeTreemapProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
}

// Color mapping for anomaly levels
function getTreemapColor(anomalyLevel: VolumeSpikeAnomalyLevel): string {
  const colors: Record<VolumeSpikeAnomalyLevel, string> = {
    very_high: "hsl(0 84% 60%)",
    high: "hsl(25 95% 53%)",
    elevated: "hsl(45 93% 47%)",
    normal: "hsl(var(--muted-foreground))",
  }
  return colors[anomalyLevel] || colors.normal
}

// Custom content renderer for treemap cells
function CustomizedContent({
  x,
  y,
  width,
  height,
  name,
  anomaly_level,
  depth,
}: {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  anomaly_level?: VolumeSpikeAnomalyLevel
  depth?: number
}) {
  if (
    typeof x !== "number" ||
    typeof y !== "number" ||
    typeof width !== "number" ||
    typeof height !== "number"
  ) {
    return null
  }

  const isIndustry = depth === 1
  const fontSize = isIndustry ? 11 : 10
  const fontWeight = isIndustry ? 600 : 400
  const fillColor = isIndustry
    ? "hsl(var(--muted))"
    : getTreemapColor(anomaly_level || "normal")

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: fillColor,
          stroke: "hsl(var(--background))",
          strokeWidth: 2,
        }}
      />
      {width > 35 && height > 18 && name && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          dominantBaseline="central"
          fill="hsl(var(--foreground))"
          fontSize={fontSize}
          fontWeight={fontWeight}
          className="pointer-events-none"
        >
          {name.length > 8 ? name.slice(0, 7) + "…" : name}
        </text>
      )}
    </g>
  )
}

// Custom tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: { name: string; size: number; anomaly_level?: string } }>
}) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1">
        <p className="font-semibold text-sm">{data.name}</p>
        <div className="text-xs">
          <span className="text-muted-foreground">Tỷ lệ: </span>
          <span className="font-medium">{data.size.toFixed(1)}x</span>
        </div>
        {data.anomaly_level && (
          <div className="text-xs">
            <span className="text-muted-foreground">Mức độ: </span>
            <span className="font-medium">
              {data.anomaly_level === "very_high"
                ? ">3x"
                : data.anomaly_level === "high"
                ? "2-3x"
                : "1.5-2x"}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export const VolumeSpikeTreemap = memo(function VolumeSpikeTreemap({ industries, className }: VolumeSpikeTreemapProps) {
  const treemapData = useMemo(() => {
    if (!industries?.length) return []
    return industries.map((ind) => ({
      name: ind.icb_name.length > 15 ? ind.icb_name.slice(0, 13) + "…" : ind.icb_name,
      children: ind.stocks.slice(0, 8).map((s) => ({
        name: s.symbol,
        size: s.spike_ratio,
        anomaly_level: s.anomaly_level,
      })),
    }))
  }, [industries])

  if (treemapData.length === 0) return null

  return (
    <Card className={cn("w-full hidden md:block", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Phân bố phân cấp theo ngành</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <Treemap
            data={treemapData}
            dataKey="size"
            aspectRatio={4 / 3}
            stroke="hsl(var(--background))"
            content={<CustomizedContent />}
          >
            <Tooltip content={<CustomTooltip />} />
          </Treemap>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
})

export function VolumeSpikeTreemapSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full hidden md:block", className)}>
      <CardHeader className="pb-2">
        <div className="h-5 w-48 bg-muted animate-pulse rounded" />
      </CardHeader>
      <CardContent>
        <div className="h-[350px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
