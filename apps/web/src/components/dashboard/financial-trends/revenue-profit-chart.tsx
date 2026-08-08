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
import { formatBillions } from "@/lib/format"
import { CHART_GRID_PROPS, CHART_TOOLTIP_STYLE } from "@/lib/chart-theme"

interface RevenueProfitChartProps {
  data: TrendMetricsResponse
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
        <CartesianGrid {...CHART_GRID_PROPS} />
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
          contentStyle={CHART_TOOLTIP_STYLE}
          formatter={(value, name) => {
            const labels: Record<string, string> = {
              revenue: "Doanh thu",
              gross_profit: "LN gộp",
              net_profit: "LN ròng",
            }
            return [formatBillions(value as number), labels[name as string] || name]
          }}
        />
        <Legend
          formatter={(value) => {
            const labels: Record<string, string> = {
              revenue: "Doanh thu",
              gross_profit: "LN gộp",
              net_profit: "LN ròng",
            }
            return <span style={{ color: "hsl(var(--foreground))", fontSize: 12 }}>{labels[value] || value}</span>
          }}
          wrapperStyle={{ paddingTop: 16 }}
          iconSize={10}
        />
        {/* Doanh thu first (largest) */}
        <Bar
          yAxisId="left"
          dataKey="revenue"
          name="revenue"
          fill="hsl(0 0% 100%)"
          radius={[4, 4, 0, 0]}
        />
        {/* LN gộp second */}
        <Bar
          yAxisId="left"
          dataKey="gross_profit"
          name="gross_profit"
          fill="hsl(var(--primary))"
          radius={[4, 4, 0, 0]}
        />
        {/* LN ròng as line */}
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="net_profit"
          name="net_profit"
          stroke="hsl(var(--accent-green))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--accent-green))", strokeWidth: 2, r: 3 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
