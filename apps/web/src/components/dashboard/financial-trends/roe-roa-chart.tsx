"use client"

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface RoeRoaChartProps {
  data: TrendMetricsResponse
}

export function RoeRoaChart({ data }: RoeRoaChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    roe: data.roe[i] ? data.roe[i]! * 100 : null,
    roa: data.roa[i] ? data.roa[i]! * 100 : null,
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value) => [`${(value as number)?.toFixed(1)}%`]}
        />
        <Legend />
        <ReferenceLine
          y={15}
          stroke="hsl(var(--muted-foreground))"
          strokeDasharray="3 3"
          label={{ value: "Benchmark 15%", position: "right", fontSize: 10 }}
        />
        <Line
          type="monotone"
          dataKey="roe"
          name="ROE"
          stroke="hsl(0 0% 100%)"
          strokeWidth={2}
          dot={{ fill: "hsl(0 0% 100%)", strokeWidth: 2 }}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="roa"
          name="ROA"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--muted-foreground))", strokeWidth: 2 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
