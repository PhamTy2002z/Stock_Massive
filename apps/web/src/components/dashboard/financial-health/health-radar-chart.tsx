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
        <PolarGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Radar
          name="Score"
          dataKey="score"
          stroke="hsl(var(--accent-orange))"
          fill="hsl(var(--accent-orange))"
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
