"use client"

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface MarginTrendChartProps {
  data: TrendMetricsResponse
}

export function MarginTrendChart({ data }: MarginTrendChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    gross_margin: data.gross_margin[i] ? data.gross_margin[i]! * 100 : null,
    net_margin: data.net_margin[i] ? data.net_margin[i]! * 100 : null,
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <defs>
          <linearGradient id="grossMarginGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(0 0% 100%)" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(0 0% 100%)" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="netMarginGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0} />
          </linearGradient>
        </defs>
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
          formatter={(value, name) => [
            `${(value as number)?.toFixed(1)}%`,
            name === "gross_margin" ? "Biên LN gộp" : "Biên LN ròng",
          ]}
        />
        <Legend
          formatter={(value) =>
            value === "gross_margin" ? "Biên LN gộp" : "Biên LN ròng"
          }
        />
        <Area
          type="monotone"
          dataKey="gross_margin"
          stroke="hsl(0 0% 100%)"
          fill="url(#grossMarginGradient)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="net_margin"
          stroke="hsl(var(--muted-foreground))"
          fill="url(#netMarginGradient)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
