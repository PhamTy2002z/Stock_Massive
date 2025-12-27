"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { TradingStatsResponse } from "@/lib/api"

interface TradingStatsCardProps {
  data: TradingStatsResponse | undefined
  isLoading: boolean
}

function formatVolume(value: number | null): string {
  if (value === null || value === undefined) return "N/A"
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(2)}M`
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}K`
  }
  return value.toLocaleString("vi-VN")
}

function formatValue(value: number | null): string {
  if (value === null || value === undefined) return "N/A"
  if (value >= 1000000000) {
    return `${(value / 1000000000).toFixed(2)} tỷ`
  }
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(2)} triệu`
  }
  return value.toLocaleString("vi-VN")
}

function formatPrice(value: number | null): string {
  if (value === null || value === undefined) return "N/A"
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function TradingStatsCard({ data, isLoading }: TradingStatsCardProps) {
  if (isLoading) {
    return <TradingStatsCardSkeleton />
  }

  const stats = [
    {
      label: "Tổng KL",
      value: formatVolume(data?.total_volume ?? null),
      description: "Tổng khối lượng giao dịch",
    },
    {
      label: "KL TB",
      value: formatVolume(data?.avg_volume ?? null),
      description: "Khối lượng trung bình",
    },
    {
      label: "Tổng GTGD",
      value: formatValue(data?.total_value ?? null),
      description: "Tổng giá trị giao dịch",
    },
    {
      label: "GTGD TB",
      value: formatValue(data?.avg_value ?? null),
      description: "Giá trị giao dịch trung bình",
    },
    {
      label: "Giá cao",
      value: formatPrice(data?.high_price ?? null),
      description: "Giá cao nhất",
    },
    {
      label: "Giá thấp",
      value: formatPrice(data?.low_price ?? null),
      description: "Giá thấp nhất",
    },
  ]

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Thống Kê Giao Dịch</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {stats.map(({ label, value, description }) => (
            <div
              key={label}
              className="flex items-center justify-between"
              title={description}
            >
              <span className="text-sm text-muted-foreground">{label}</span>
              <span className="text-sm font-medium tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function TradingStatsCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <Skeleton className="h-5 w-36" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export { TradingStatsCardSkeleton }
