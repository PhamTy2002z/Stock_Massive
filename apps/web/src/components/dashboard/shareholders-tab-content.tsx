"use client"

import { useState, useMemo } from "react"
import { cn } from "@/lib/utils"
import { ChevronLeft, ChevronRight } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useShareholders } from "@/hooks/use-shareholders"

interface ShareholdersTabContentProps {
  symbol?: string
  className?: string
}

// Format shares - convert to millions with "triệu" unit
function formatShares(value: number): string {
  const millions = value / 1_000_000
  return `${millions.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} triệu`
}

// Format percentage
function formatPercent(value: number): string {
  return `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`
}

export function ShareholdersTabContent({
  symbol = "HAG",
  className,
}: ShareholdersTabContentProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)

  const { data, isLoading, error } = useShareholders(symbol)

  // Calculate pagination
  const shareholders = data?.shareholders ?? []
  const totalItems = shareholders.length
  const totalPages = Math.max(1, Math.ceil(totalItems / rowsPerPage))
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems)

  // Get current page data
  const currentData = useMemo(() => {
    return shareholders.slice(startIndex, endIndex)
  }, [shareholders, startIndex, endIndex])

  // Handle page change
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  // Handle rows per page change
  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(Number(value))
    setCurrentPage(1) // Reset to first page
  }

  // Show skeleton while loading
  if (isLoading) {
    return <ShareholdersTabContentSkeleton className={className} />
  }

  // Show error state
  if (error) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">
            Không thể tải dữ liệu cổ đông: {error.message}
          </p>
        </div>
      </div>
    )
  }

  // Show empty state
  if (totalItems === 0) {
    return (
      <div className={cn("space-y-4", className)}>
        <h3 className="text-sm text-muted-foreground">
          Danh sách cổ đông lớn của {symbol}
        </h3>
        <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
          <p className="text-sm text-muted-foreground">
            Không có dữ liệu cổ đông cho mã {symbol}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Title */}
      <h3 className="text-sm text-muted-foreground">
        Danh sách cổ đông lớn của {symbol}
      </h3>

      {/* Table */}
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[600px] border-collapse">
            <thead>
              <tr className="border-b border-border/50 bg-muted/30">
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  Cổ đông
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Số lượng
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Tỷ lệ sở hữu
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Ngày cập nhật
                </th>
              </tr>
            </thead>
            <tbody>
              {currentData.map((shareholder) => (
                <tr
                  key={shareholder.id}
                  className="border-b border-border/30 transition-colors hover:bg-muted/20"
                >
                  <td className="py-3 px-4 text-sm font-medium text-foreground">
                    {shareholder.name}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                    {formatShares(shareholder.shares)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                    {formatPercent(shareholder.ownership_pct)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-muted-foreground">
                    {shareholder.update_date ?? "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/50 bg-muted/20">
          {/* Items info */}
          <span className="text-sm text-muted-foreground">
            {startIndex + 1}-{endIndex} trên {totalItems} cổ đông
          </span>

          {/* Right side controls */}
          <div className="flex items-center gap-4">
            {/* Rows per page */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                Hàng mỗi trang
              </span>
              <Select
                value={String(rowsPerPage)}
                onValueChange={handleRowsPerPageChange}
              >
                <SelectTrigger className="w-[70px] h-8 text-sm bg-background border-border/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Page navigation */}
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

// Skeleton for loading state
export function ShareholdersTabContentSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)}>
      {/* Title skeleton */}
      <div className="h-5 w-64 rounded bg-muted animate-pulse" />

      {/* Table skeleton */}
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
        {/* Header */}
        <div className="flex gap-4 pb-2 border-b border-border/30">
          <div className="h-4 w-32 rounded bg-muted animate-pulse" />
          <div className="h-4 w-20 rounded bg-muted animate-pulse ml-auto" />
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
        </div>
        {/* Rows */}
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-48 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse ml-auto" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  )
}
