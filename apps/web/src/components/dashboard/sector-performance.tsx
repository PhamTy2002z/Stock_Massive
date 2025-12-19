"use client"

import { useState } from "react"
import { useSectorPerformance } from "@/hooks/use-sector-performance"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, RefreshCw, TrendingUp, TrendingDown, ArrowUpDown } from "lucide-react"
import { cn } from "@/lib/utils"

type SortField = "change_pct" | "total_market_cap" | "stock_count" | "icb_name"
type SortOrder = "asc" | "desc"

interface SectorPerformanceProps {
  className?: string
}

export function SectorPerformance({ className }: SectorPerformanceProps) {
  const { data, isLoading, error, refetch, lastUpdated } = useSectorPerformance()
  const [sortField, setSortField] = useState<SortField>("change_pct")
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc")

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortOrder("desc")
    }
  }

  const sortedSectors = data?.sectors
    ? [...data.sectors].sort((a, b) => {
        const aVal = a[sortField]
        const bVal = b[sortField]
        if (typeof aVal === "string" && typeof bVal === "string") {
          return sortOrder === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
        }
        return sortOrder === "asc" ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number)
      })
    : []

  if (isLoading && !data) {
    return <SectorPerformanceSkeleton />
  }

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm text-muted-foreground mb-3">{error.message}</p>
        <button
          onClick={refetch}
          className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    )
  }

  if (!data || data.sectors.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">No sector data available</p>
      </div>
    )
  }

  return (
    <div className={cn("rounded-xl border bg-card", className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <h3 className="font-semibold">Hiệu suất ngành</h3>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Cập nhật: {lastUpdated.toLocaleTimeString("vi-VN")}
            </span>
          )}
          <button
            onClick={refetch}
            disabled={isLoading}
            className="p-1.5 rounded-md hover:bg-muted transition-colors"
            title="Làm mới"
            aria-label="Làm mới dữ liệu"
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3 font-medium">
                <button
                  onClick={() => handleSort("icb_name")}
                  className="inline-flex items-center gap-1 hover:text-foreground text-muted-foreground"
                >
                  Ngành
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-right p-3 font-medium">
                <button
                  onClick={() => handleSort("change_pct")}
                  className="inline-flex items-center gap-1 hover:text-foreground text-muted-foreground ml-auto"
                >
                  Thay đổi %
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-right p-3 font-medium">
                <button
                  onClick={() => handleSort("total_market_cap")}
                  className="inline-flex items-center gap-1 hover:text-foreground text-muted-foreground ml-auto"
                >
                  Vốn hóa
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-right p-3 font-medium">
                <button
                  onClick={() => handleSort("stock_count")}
                  className="inline-flex items-center gap-1 hover:text-foreground text-muted-foreground ml-auto"
                >
                  Số CP
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-left p-3 font-medium hidden lg:table-cell text-muted-foreground">
                Top tăng/giảm
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedSectors.map((sector) => (
              <tr key={sector.icb_code} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                <td className="p-3">
                  <div className="font-medium">{sector.icb_name}</div>
                  <div className="text-xs text-muted-foreground">{sector.icb_code}</div>
                </td>
                <td className="p-3 text-right">
                  <div
                    className={cn(
                      "inline-flex items-center gap-1 font-medium tabular-nums",
                      sector.change_pct > 0 && "text-green-600 dark:text-green-400",
                      sector.change_pct < 0 && "text-red-600 dark:text-red-400",
                      sector.change_pct === 0 && "text-muted-foreground"
                    )}
                  >
                    {sector.change_pct > 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : sector.change_pct < 0 ? (
                      <TrendingDown className="h-4 w-4" />
                    ) : null}
                    {sector.change_pct > 0 ? "+" : ""}
                    {sector.change_pct.toFixed(2)}%
                  </div>
                </td>
                <td className="p-3 text-right text-muted-foreground tabular-nums">
                  {formatMarketCap(sector.total_market_cap)}
                </td>
                <td className="p-3 text-right text-muted-foreground tabular-nums">
                  {sector.stock_count}
                </td>
                <td className="p-3 hidden lg:table-cell">
                  <div className="flex gap-2 text-xs flex-wrap">
                    {sector.top_gainers.slice(0, 2).map((s) => (
                      <span key={s} className="text-green-600 dark:text-green-400 font-medium">
                        {s}
                      </span>
                    ))}
                    {sector.top_losers.slice(0, 2).map((s) => (
                      <span key={s} className="text-red-600 dark:text-red-400 font-medium">
                        {s}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SectorPerformanceSkeleton() {
  return (
    <div className="rounded-xl border bg-card">
      <div className="flex items-center justify-between p-4 border-b">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>
      <div className="p-4 space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-16 ml-auto" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-12" />
          </div>
        ))}
      </div>
    </div>
  )
}

function formatMarketCap(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}T`
  }
  return `${value.toFixed(0)}B`
}

export { SectorPerformanceSkeleton }
