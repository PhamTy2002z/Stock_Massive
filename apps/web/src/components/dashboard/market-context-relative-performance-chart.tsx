"use client"

import { useMemo } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { MarketContextChartDataPoint } from "@/lib/api"

interface RelativePerformanceChartProps {
  data: MarketContextChartDataPoint[]
  symbol: string
  hasSector: boolean
}

export function RelativePerformanceChart({
  data,
  symbol,
  hasSector,
}: RelativePerformanceChartProps) {
  // Transform data for Recharts with localized date labels
  const chartData = useMemo(() => {
    return data.map((point) => ({
      date: new Date(point.date).toLocaleDateString("vi-VN", {
        month: "short",
        day: "numeric",
      }),
      [symbol]: point.stock,
      VNINDEX: point.vnindex,
      ...(hasSector && point.sector !== null ? { Sector: point.sector } : {}),
    }))
  }, [data, symbol, hasSector])

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Hiệu Suất Tương Đối</CardTitle>
        <CardDescription>
          Chuẩn hóa 100 tại điểm bắt đầu
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[350px] sm:h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 10, left: -10, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                className="stroke-muted"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => value.toFixed(0)}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                formatter={(value) => [(value as number).toFixed(2), ""]}
                labelStyle={{ color: "hsl(var(--foreground))" }}
              />
              <Legend
                wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }}
              />
              <Line
                type="monotone"
                dataKey={symbol}
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                name={symbol}
              />
              <Line
                type="monotone"
                dataKey="VNINDEX"
                stroke="hsl(var(--muted-foreground))"
                strokeWidth={2}
                dot={false}
                strokeDasharray="5 5"
                activeDot={{ r: 4, strokeWidth: 0 }}
                name="VNINDEX"
              />
              {hasSector && (
                <Line
                  type="monotone"
                  dataKey="Sector"
                  stroke="hsl(var(--chart-2))"
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="3 3"
                  activeDot={{ r: 4, strokeWidth: 0 }}
                  name="Ngành"
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

// Skeleton for loading state
export function RelativePerformanceChartSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="h-5 w-40 bg-muted animate-pulse rounded" />
        <div className="h-4 w-56 bg-muted animate-pulse rounded mt-1" />
      </CardHeader>
      <CardContent>
        <div className="h-[350px] sm:h-[400px] bg-muted/50 animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
