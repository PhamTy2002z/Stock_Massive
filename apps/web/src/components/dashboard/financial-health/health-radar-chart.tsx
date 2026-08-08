"use client"

import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Tooltip } from "recharts"
import type { HealthScoreDimension } from "@/lib/api"
import { CHART_TOOLTIP_STYLE } from "@/lib/chart-theme"

interface HealthRadarChartProps {
  dimensions: Record<string, HealthScoreDimension>
}

const DIMENSION_LABELS: Record<string, string> = {
  profitability: "Sinh lời",
  liquidity: "Thanh khoản",
  leverage: "Đòn bẩy",
  efficiency: "Hiệu quả",
  valuation: "Định giá",
}

// Custom tick with dynamic positioning based on angle
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTick(props: any) {
  const { x = 0, y = 0, payload, cx = 0, cy = 0 } = props
  const label = payload?.value ?? ""

  // Calculate angle from center to determine optimal label position
  const angle = Math.atan2(y - cy, x - cx)
  const angleDeg = (angle * 180) / Math.PI

  // Dynamic offset based on position - push labels outward
  const offsetDistance = 12
  const offsetX = Math.cos(angle) * offsetDistance
  const offsetY = Math.sin(angle) * offsetDistance

  // Determine text anchor based on angle
  let textAnchor: "start" | "middle" | "end" = "middle"
  if (angleDeg > 45 && angleDeg < 135) {
    // Bottom
    textAnchor = "middle"
  } else if (angleDeg >= 135 || angleDeg <= -135) {
    // Left side
    textAnchor = "end"
  } else if (angleDeg > -135 && angleDeg < -45) {
    // Top
    textAnchor = "middle"
  } else {
    // Right side
    textAnchor = "start"
  }

  return (
    <text
      x={x + offsetX}
      y={y + offsetY}
      fill="hsl(var(--muted-foreground))"
      fontSize={11}
      textAnchor={textAnchor}
      dominantBaseline="central"
    >
      {label}
    </text>
  )
}

export function HealthRadarChart({ dimensions }: HealthRadarChartProps) {
  const data = Object.entries(dimensions).map(([key, dim]) => ({
    dimension: DIMENSION_LABELS[key] || key,
    score: dim.score,
    fullMark: 100,
  }))

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} margin={{ top: 40, right: 80, bottom: 40, left: 60 }} outerRadius="65%">
        <PolarGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <PolarAngleAxis dataKey="dimension" tick={(props) => <CustomTick {...props} />} />
        <Radar
          name="Score"
          dataKey="score"
          stroke="hsl(0 0% 100%)"
          fill="hsl(0 0% 100%)"
          fillOpacity={0.3}
          strokeWidth={2}
        />
        <Tooltip
          contentStyle={CHART_TOOLTIP_STYLE}
          formatter={(value) => [`${value}/100`, "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
