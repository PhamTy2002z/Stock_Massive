"use client"

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
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface RevenueProfitChartProps {
  data: TrendMetricsResponse
}

function formatBillions(value: number): string {
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toLocaleString()
}

export function RevenueProfitChart({ data }: RevenueProfitChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    revenue: data.revenue[i],
    gross_profit: data.gross_profit[i],
    net_profit: data.net_profit[i],
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          yAxisId="left"
          tickFormatter={formatBillions}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value, name) => {
            const labels: Record<string, string> = {
              revenue: "Doanh thu",
              gross_profit: "LN gop",
              net_profit: "LN rong",
            }
            return [formatBillions(value as number), labels[name as string] || name]
          }}
        />
        <Legend
          formatter={(value) => {
            const labels: Record<string, string> = {
              revenue: "Doanh thu",
              gross_profit: "LN gop",
              net_profit: "LN rong",
            }
            return labels[value] || value
          }}
        />
        <Bar
          yAxisId="left"
          dataKey="revenue"
          fill="hsl(var(--accent-orange))"
          radius={[4, 4, 0, 0]}
        />
        <Bar
          yAxisId="left"
          dataKey="gross_profit"
          fill="hsl(var(--accent-orange) / 0.6)"
          radius={[4, 4, 0, 0]}
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="net_profit"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--muted-foreground))", strokeWidth: 2 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
