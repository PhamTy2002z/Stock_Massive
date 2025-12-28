"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts"
import { Skeleton } from "@/components/ui/skeleton"
import type { PropTradingItem } from "@/lib/api"

interface PropFlowChartProps {
  data: PropTradingItem[] | undefined
  isLoading: boolean
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })
}

function formatVolume(value: number): string {
  if (Math.abs(value) >= 1000000) {
    return `${(value / 1000000).toFixed(2)}M`
  }
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return value.toLocaleString("vi-VN")
}

export function PropFlowChart({ data, isLoading }: PropFlowChartProps) {
  if (isLoading) {
    return <PropFlowChartSkeleton />
  }

  if (!data || !Array.isArray(data) || data.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-sm">Dữ liệu giao dịch tự doanh chưa khả dụng</p>
        <p className="text-xs mt-1 opacity-70">Tính năng đang được phát triển</p>
      </div>
    )
  }

  const chartData = data.map((item) => ({
    date: formatDate(item.date),
    net_volume: item.net_volume,
    buy_volume: item.buy_volume,
    sell_volume: item.sell_volume,
  }))

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => formatVolume(value)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value, name) => {
              const numValue = typeof value === "number" ? value : 0
              if (name === "net_volume") {
                return [formatVolume(numValue), "KL ròng"]
              }
              return [formatVolume(numValue), String(name)]
            }}
            labelFormatter={(label) => `Ngày: ${label}`}
          />
          <ReferenceLine y={0} stroke="hsl(var(--border))" />
          <Bar dataKey="net_volume" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={
                  entry.net_volume >= 0
                    ? "hsl(142 76% 36%)" // green-600
                    : "hsl(0 84% 60%)" // red-500
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-border/50">
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Tổng mua</p>
          <p className="text-sm font-medium text-green-600 dark:text-green-400">
            {formatVolume(data.reduce((sum, d) => sum + d.buy_volume, 0))}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Tổng bán</p>
          <p className="text-sm font-medium text-red-600 dark:text-red-400">
            {formatVolume(data.reduce((sum, d) => sum + d.sell_volume, 0))}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-foreground">KL ròng</p>
          <p
            className={`text-sm font-medium ${
              data.reduce((sum, d) => sum + d.net_volume, 0) >= 0
                ? "text-green-600 dark:text-green-400"
                : "text-red-600 dark:text-red-400"
            }`}
          >
            {formatVolume(data.reduce((sum, d) => sum + d.net_volume, 0))}
          </p>
        </div>
      </div>
    </div>
  )
}

function PropFlowChartSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-[280px] w-full" />
      <div className="grid grid-cols-3 gap-4 pt-4 border-t border-border/50">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="text-center space-y-2">
            <Skeleton className="h-3 w-16 mx-auto" />
            <Skeleton className="h-4 w-20 mx-auto" />
          </div>
        ))}
      </div>
    </div>
  )
}

export { PropFlowChartSkeleton }
