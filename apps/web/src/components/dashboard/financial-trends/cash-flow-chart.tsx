"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"
import { formatBillions } from "@/lib/format"
import { CHART_GRID_PROPS, CHART_TOOLTIP_STYLE } from "@/lib/chart-theme"

interface CashFlowChartProps {
  data: TrendMetricsResponse
}

export function CashFlowChart({ data }: CashFlowChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    cfo: data.cfo[i],
    cfi: data.cfi[i],
    cff: data.cff[i],
  }))

  const labels: Record<string, string> = {
    cfo: "HĐ kinh doanh",
    cfi: "HĐ đầu tư",
    cff: "HĐ tài chính",
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid {...CHART_GRID_PROPS} />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={formatBillions}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={CHART_TOOLTIP_STYLE}
          formatter={(value, name) => [
            formatBillions(value as number),
            labels[name as string] || name,
          ]}
        />
        <Legend
          formatter={(value) => (
            <span style={{ color: "hsl(var(--foreground))", fontSize: 12 }}>{labels[value] || value}</span>
          )}
          wrapperStyle={{ paddingTop: 16 }}
          iconSize={10}
        />
        <ReferenceLine y={0} stroke="hsl(var(--foreground))" />
        <Bar dataKey="cfo" fill="hsl(0 0% 100%)" radius={[4, 4, 0, 0]} />
        <Bar dataKey="cfi" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
        <Bar dataKey="cff" fill="hsl(var(--border))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
