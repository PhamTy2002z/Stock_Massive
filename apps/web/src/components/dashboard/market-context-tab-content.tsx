"use client"

import { useState } from "react"
import { useMarketContext } from "@/hooks/use-market-context"
import { PeriodSelector } from "./market-context-period-selector"
import {
  RelativePerformanceChart,
  RelativePerformanceChartSkeleton,
} from "./market-context-relative-performance-chart"
import {
  CorrelationCard,
  CorrelationCardSkeleton,
} from "./market-context-correlation-card"
import {
  SectorContextCard,
  SectorContextCardSkeleton,
} from "./market-context-sector-card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AlertCircle, TrendingUp, TrendingDown, RefreshCw } from "lucide-react"
import type { MarketContextPeriod } from "@/lib/api"

interface MarketContextTabContentProps {
  symbol: string
}

export function MarketContextTabContent({
  symbol,
}: MarketContextTabContentProps) {
  const [period, setPeriod] = useState<MarketContextPeriod>("3M")
  const { data, isLoading, error, refetch, isFetching } = useMarketContext(
    symbol,
    period
  )

  // Loading state
  if (isLoading) {
    return <MarketContextTabSkeleton />
  }

  // Error state - show friendly message for missing data
  if (error) {
    const isNoDataError = error.message?.includes("400") || error.message?.includes("No data")

    if (isNoDataError) {
      return (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Đang cập nhật dữ liệu</AlertTitle>
          <AlertDescription>
            Dữ liệu ngữ cảnh thị trường cho mã {symbol} đang được tính toán.
            Hệ thống chạy EOD pipeline hàng ngày lúc 15:30 ICT.
            Vui lòng thử lại sau.
          </AlertDescription>
        </Alert>
      )
    }

    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Lỗi</AlertTitle>
        <AlertDescription className="flex items-center gap-2">
          Không thể tải dữ liệu ngữ cảnh thị trường.
          <Button
            variant="link"
            size="sm"
            onClick={() => refetch()}
            className="h-auto p-0 underline"
          >
            Thử lại
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  // No data
  if (!data) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Không có dữ liệu</AlertTitle>
        <AlertDescription>
          Chưa có dữ liệu ngữ cảnh thị trường cho mã {symbol}.
        </AlertDescription>
      </Alert>
    )
  }

  const hasSector = data.sector !== null

  return (
    <div className="space-y-6">
      {/* Header with Period Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            Ngữ Cảnh Thị Trường
            {isFetching && (
              <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </h3>
          <p className="text-sm text-muted-foreground">
            Phân tích biến động so với thị trường và ngành
          </p>
        </div>
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>

      {/* Performance Summary Badges */}
      <div className="flex flex-wrap gap-2">
        <Badge
          variant={data.performance.outperform_market ? "default" : "secondary"}
          className="gap-1"
        >
          {data.performance.outperform_market ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {data.performance.outperform_market
            ? "Vượt trội thị trường"
            : "Yếu hơn thị trường"}
        </Badge>

        {data.performance.outperform_sector !== null && (
          <Badge
            variant={
              data.performance.outperform_sector ? "default" : "secondary"
            }
            className="gap-1"
          >
            {data.performance.outperform_sector ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {data.performance.outperform_sector
              ? "Vượt trội ngành"
              : "Yếu hơn ngành"}
          </Badge>
        )}

        <Badge variant="outline">
          CP:{" "}
          {(data.performance.stock_return ?? 0) >= 0 ? "+" : ""}
          {(data.performance.stock_return ?? 0).toFixed(2)}%
        </Badge>
        <Badge variant="outline">
          TT:{" "}
          {(data.performance.vnindex_return ?? 0) >= 0 ? "+" : ""}
          {(data.performance.vnindex_return ?? 0).toFixed(2)}%
        </Badge>
        {data.performance.sector_return !== null && (
          <Badge variant="outline">
            Ngành:{" "}
            {data.performance.sector_return >= 0 ? "+" : ""}
            {data.performance.sector_return.toFixed(2)}%
          </Badge>
        )}
      </div>

      {/* Chart */}
      <RelativePerformanceChart
        data={data.chart_data}
        symbol={symbol}
        hasSector={hasSector}
      />

      {/* Metrics Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        <CorrelationCard metrics={data.metrics} />
        <SectorContextCard sector={data.sector} />
      </div>
    </div>
  )
}

// Skeleton for loading state
function MarketContextTabSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-2">
          <div className="h-6 w-40 bg-muted animate-pulse rounded" />
          <div className="h-4 w-64 bg-muted animate-pulse rounded" />
        </div>
        <div className="h-9 w-52 bg-muted animate-pulse rounded" />
      </div>
      <div className="flex flex-wrap gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-6 w-28 bg-muted animate-pulse rounded-full"
          />
        ))}
      </div>
      <RelativePerformanceChartSkeleton />
      <div className="grid gap-6 md:grid-cols-2">
        <CorrelationCardSkeleton />
        <SectorContextCardSkeleton />
      </div>
    </div>
  )
}

// Re-export skeleton for external use
export { MarketContextTabSkeleton }
