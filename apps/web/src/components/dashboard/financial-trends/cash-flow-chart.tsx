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

interface CashFlowChartProps {
  data: TrendMetricsResponse
}

function formatBillions(value: number): string {
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toLocaleString()
}

export function CashFlowChart({ data }: CashFlowChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    cfo: data.cfo[i],
    cfi: data.cfi[i],
    cff: data.cff[i],
  }))

  const labels: Record<string, string> = {
    cfo: "Hoat dong KD",
    cfi: "Hoat dong DT",
    cff: "Hoat dong TC",
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={formatBillions}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value, name) => [
            formatBillions(value as number),
            labels[name as string] || name,
          ]}
        />
        <Legend formatter={(value) => labels[value] || value} />
        <ReferenceLine y={0} stroke="hsl(var(--foreground))" />
        <Bar dataKey="cfo" fill="hsl(var(--accent-orange))" radius={[4, 4, 0, 0]} />
        <Bar dataKey="cfi" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
        <Bar dataKey="cff" fill="hsl(var(--border))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
