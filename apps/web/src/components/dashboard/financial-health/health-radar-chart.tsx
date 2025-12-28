"use client"

import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Tooltip } from "recharts"
import type { HealthScoreDimension } from "@/lib/api"

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

// Custom tick to adjust label positions
function CustomTick({ x, y, payload }: { x: number; y: number; payload: { value: string } }) {
  const label = payload.value
  // Shift "Thanh khoản" to the right to avoid overlap
  const offsetX = label === "Thanh khoản" ? 10 : 0

  return (
    <text
      x={x + offsetX}
      y={y}
      fill="hsl(var(--muted-foreground))"
      fontSize={11}
      textAnchor="middle"
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
      <RadarChart data={data} margin={{ top: 30, right: 50, bottom: 30, left: 50 }}>
        <PolarGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <PolarAngleAxis dataKey="dimension" tick={<CustomTick x={0} y={0} payload={{ value: "" }} />} />
        <Radar
          name="Score"
          dataKey="score"
          stroke="hsl(0 0% 100%)"
          fill="hsl(0 0% 100%)"
          fillOpacity={0.3}
          strokeWidth={2}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value) => [`${value}/100`, "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
