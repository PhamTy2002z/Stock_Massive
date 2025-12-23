"use client"

import { useState, useMemo, memo, useCallback } from "react"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown, RefreshCw } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useVN30Overview } from "@/hooks/use-vn30-overview"

interface VN30OverviewTableProps {
  className?: string
}

function formatPrice(value: number | null): string {
  if (value === null) return "-"
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
}

function formatPercent(value: number | null): string {
  if (value === null) return "-"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`
}

function formatVolume(value: number | null): string {
  if (value === null) return "-"
  const millions = value / 1_000_000
  return `${millions.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}M`
}

function formatMarketCap(value: number | null): string {
  if (value === null) return "-"
  return `${value.toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })} tỷ`
}

type SortDirection = "asc" | "desc" | null

// Memoized row component to prevent unnecessary re-renders
interface VN30RowProps {
  stock: {
    symbol: string
    company_name: string
    price: number | null
    change_pct: number | null
    volume: number | null
    market_cap: number | null
  }
}

const VN30Row = memo(function VN30Row({ stock }: VN30RowProps) {
  const isPositive = (stock.change_pct ?? 0) >= 0
  const changeColor = isPositive
    ? "text-green-500 dark:text-green-400"
    : "text-red-500 dark:text-red-400"

  return (
    <tr className="border-b border-border/30 transition-colors hover:bg-muted/20">
      <td className="py-3 px-4 text-sm font-semibold text-foreground">
        {stock.symbol}
      </td>
      <td className="py-3 px-4 text-sm text-foreground/90">
        {stock.company_name}
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums font-medium text-foreground">
        {formatPrice(stock.price)}
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums">
        <div className="flex items-center justify-end gap-1">
          {stock.change_pct !== null && (
            isPositive ? (
              <TrendingUp className={cn("h-3.5 w-3.5", changeColor)} />
            ) : (
              <TrendingDown className={cn("h-3.5 w-3.5", changeColor)} />
            )
          )}
          <span className={cn("font-medium", changeColor)}>
            {formatPercent(stock.change_pct)}
          </span>
        </div>
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
        {formatVolume(stock.volume)}
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
        {formatMarketCap(stock.market_cap)}
      </td>
    </tr>
  )
})

export function VN30OverviewTable({ className }: VN30OverviewTableProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)
  const [sortDirection, setSortDirection] = useState<SortDirection>(null)

  const { data, isLoading, isFetching, error, refetch } = useVN30Overview()

  const stocks = useMemo(() => {
    const rawStocks = data?.stocks ?? []
    if (sortDirection === null) return rawStocks

    return [...rawStocks].sort((a, b) => {
      const aVal = a.change_pct ?? -Infinity
      const bVal = b.change_pct ?? -Infinity
      return sortDirection === "asc" ? aVal - bVal : bVal - aVal
    })
  }, [data?.stocks, sortDirection])

  const toggleSort = useCallback(() => {
    setSortDirection((prev) => {
      if (prev === null) return "desc"
      if (prev === "desc") return "asc"
      return null
    })
    setCurrentPage(1)
  }, [])
  const totalItems = stocks.length
  const totalPages = Math.max(1, Math.ceil(totalItems / rowsPerPage))
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems)

  const currentData = useMemo(() => {
    return stocks.slice(startIndex, endIndex)
  }, [stocks, startIndex, endIndex])

  const goToPage = useCallback((page: number) => {
    setCurrentPage((curr) => {
      if (page >= 1 && page <= totalPages) return page
      return curr
    })
  }, [totalPages])

  const handleRowsPerPageChange = useCallback((value: string) => {
    setRowsPerPage(Number(value))
    setCurrentPage(1)
  }, [])

  const handleRefetch = useCallback(() => {
    refetch()
  }, [refetch])

  if (isLoading && !data) {
    return (
      <div className={className}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Tổng quan VN30</h2>
          <button
            disabled
            className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
            title="Làm mới dữ liệu"
            aria-label="Làm mới dữ liệu"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
        <VN30OverviewTableSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Tổng quan VN30</h2>
          <button
            onClick={handleRefetch}
            disabled={isFetching}
            className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
            title="Làm mới dữ liệu"
            aria-label="Làm mới dữ liệu"
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          </button>
        </div>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">
            Không thể tải dữ liệu VN30: {error.message}
          </p>
        </div>
      </div>
    )
  }

  if (totalItems === 0) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Tổng quan VN30</h2>
          <button
            onClick={handleRefetch}
            disabled={isFetching}
            className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
            title="Làm mới dữ liệu"
            aria-label="Làm mới dữ liệu"
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          </button>
        </div>
        <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
          <p className="text-sm text-muted-foreground">Không có dữ liệu VN30</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with title and refresh button */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Tổng quan VN30</h2>
        <button
          onClick={handleRefetch}
          disabled={isFetching}
          className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
          title="Làm mới dữ liệu"
          aria-label="Làm mới dữ liệu"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[800px] border-collapse">
            <thead>
              <tr className="border-b border-border/50 bg-muted/30">
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">Mã</th>
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">Tên công ty</th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">Giá</th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  <button
                    onClick={toggleSort}
                    className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                  >
                    %
                    {sortDirection === null && <ArrowUpDown className="h-3.5 w-3.5" />}
                    {sortDirection === "desc" && <ArrowDown className="h-3.5 w-3.5" />}
                    {sortDirection === "asc" && <ArrowUp className="h-3.5 w-3.5" />}
                  </button>
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">Khối lượng</th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">Vốn hóa</th>
              </tr>
            </thead>
            <tbody>
              {currentData.map((stock) => (
                <VN30Row key={stock.symbol} stock={stock} />
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between px-4 py-3 border-t border-border/50 bg-muted/20">
          <span className="text-sm text-muted-foreground">
            {startIndex + 1}-{endIndex} trên {totalItems} cổ phiếu
          </span>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">Hàng mỗi trang</span>
              <Select value={String(rowsPerPage)} onValueChange={handleRowsPerPageChange}>
                <SelectTrigger className="w-[70px] h-8 text-sm bg-background border-border/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="30">30</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <span className="text-sm text-muted-foreground whitespace-nowrap min-w-[80px] text-center">
                Trang {currentPage}/{totalPages}
              </span>

              <button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function VN30OverviewTableSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)}>
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
        <div className="flex gap-4 pb-2 border-b border-border/30">
          <div className="h-4 w-12 rounded bg-muted animate-pulse" />
          <div className="h-4 w-40 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse ml-auto" />
          <div className="h-4 w-12 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse" />
          <div className="h-4 w-20 rounded bg-muted animate-pulse" />
        </div>
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-12 rounded bg-muted animate-pulse" />
            <div className="h-4 w-40 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse ml-auto" />
            <div className="h-4 w-12 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse" />
          </div>
        ))}
        <div className="flex justify-between pt-3 border-t border-border/30">
          <div className="h-4 w-32 rounded bg-muted animate-pulse" />
          <div className="flex gap-2">
            <div className="h-8 w-24 rounded bg-muted animate-pulse" />
            <div className="h-8 w-24 rounded bg-muted animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  )
}
