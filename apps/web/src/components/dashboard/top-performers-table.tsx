"use client"

import { useState, useMemo } from "react"
import { cn } from "@/lib/utils"
import {
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  RefreshCw,
  Play,
  Loader2,
} from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useTopPerformers } from "@/hooks/use-top-performers"
import { triggerTopPerformersCollection } from "@/lib/api"
import type { TopPerformerItem } from "@/lib/api"
import { toast } from "sonner"

interface TopPerformersTableProps {
  className?: string
}

type SortField = "rank" | "net_profit" | "revenue" | "profit_margin" | "eps"
type SortDirection = "asc" | "desc" | null

function formatProfit(value: number | null): string {
  if (value === null) return "-"
  const billions = value / 1_000_000_000
  return `${billions.toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`
}

function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function formatEps(value: number | null): string {
  if (value === null) return "-"
  return value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })
}

export function TopPerformersTable({ className }: TopPerformersTableProps) {
  const { data, isLoading, isFetching, error, refetch } = useTopPerformers(100)
  const [sortField, setSortField] = useState<SortField>("rank")
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc")
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)
  const [isCollecting, setIsCollecting] = useState(false)

  const handleRunCollection = async () => {
    setIsCollecting(true)
    const toastId = toast.loading("Starting collection... This may take 10-30 minutes.")
    try {
      const result = await triggerTopPerformersCollection()
      if (result.error) {
        toast.error(`Collection failed: ${result.error}`, { id: toastId })
      } else {
        toast.success(
          `Collection complete! ${result.success} records stored in ${result.elapsed_seconds.toFixed(0)}s`,
          { id: toastId }
        )
        refetch()
      }
    } catch (err) {
      toast.error(`Failed to start collection: ${err instanceof Error ? err.message : "Unknown error"}`, { id: toastId })
    } finally {
      setIsCollecting(false)
    }
  }

  const sortedData = useMemo(() => {
    if (!data?.data) return []
    if (sortDirection === null) return data.data

    return [...data.data].sort((a, b) => {
      const aVal = a[sortField] ?? -Infinity
      const bVal = b[sortField] ?? -Infinity
      return sortDirection === "asc" ? (aVal > bVal ? 1 : -1) : aVal < bVal ? 1 : -1
    })
  }, [data?.data, sortField, sortDirection])

  const totalItems = sortedData.length
  const totalPages = Math.max(1, Math.ceil(totalItems / rowsPerPage))
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems)
  const paginatedData = sortedData.slice(startIndex, endIndex)

  const toggleSort = (field: SortField) => {
    if (sortField !== field) {
      setSortField(field)
      setSortDirection("desc")
    } else {
      setSortDirection((prev) =>
        prev === "desc" ? "asc" : prev === "asc" ? null : "desc"
      )
    }
    setCurrentPage(1)
  }

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(Number(value))
    setCurrentPage(1)
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field)
      return <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
    if (sortDirection === "desc") return <ArrowDown className="h-3.5 w-3.5" />
    if (sortDirection === "asc") return <ArrowUp className="h-3.5 w-3.5" />
    return <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
  }

  if (isLoading && !data) {
    return (
      <div className={className}>
        <TopPerformersTableSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">
            Failed to load top performers: {error.message}
          </p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (totalItems === 0) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
          <p className="text-sm text-muted-foreground mb-4">
            No data available. Run the scheduled job to collect data.
          </p>
          <button
            onClick={handleRunCollection}
            disabled={isCollecting}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium",
              "bg-primary text-primary-foreground hover:bg-primary/90",
              "disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            )}
          >
            {isCollecting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Collecting...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Collection Job
              </>
            )}
          </button>
          <p className="mt-3 text-xs text-muted-foreground">
            Note: Collection takes 10-30 minutes to fetch all HOSE+HNX symbols.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with period info and refresh button */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {data?.period} • Updated:{" "}
          {data?.updated_at
            ? new Date(data.updated_at).toLocaleDateString("vi-VN")
            : "N/A"}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
          title="Refresh data"
          aria-label="Refresh data"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[900px] border-collapse">
            <thead>
              <tr className="border-b border-border/50 bg-muted/30">
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  <button
                    onClick={() => toggleSort("rank")}
                    className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                  >
                    # <SortIcon field="rank" />
                  </button>
                </th>
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  Symbol
                </th>
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  Company
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  <button
                    onClick={() => toggleSort("net_profit")}
                    className="inline-flex items-center gap-1 hover:text-foreground transition-colors ml-auto"
                  >
                    Net Profit <SortIcon field="net_profit" />
                  </button>
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  <button
                    onClick={() => toggleSort("revenue")}
                    className="inline-flex items-center gap-1 hover:text-foreground transition-colors ml-auto"
                  >
                    Revenue <SortIcon field="revenue" />
                  </button>
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  <button
                    onClick={() => toggleSort("profit_margin")}
                    className="inline-flex items-center gap-1 hover:text-foreground transition-colors ml-auto"
                  >
                    Margin <SortIcon field="profit_margin" />
                  </button>
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  <button
                    onClick={() => toggleSort("eps")}
                    className="inline-flex items-center gap-1 hover:text-foreground transition-colors ml-auto"
                  >
                    EPS <SortIcon field="eps" />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {paginatedData.map((item: TopPerformerItem) => (
                <tr
                  key={item.symbol}
                  className="border-b border-border/30 transition-colors hover:bg-muted/20"
                >
                  <td className="py-3 px-4 text-sm font-medium text-foreground">
                    {item.rank}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-sm font-semibold text-primary">
                      {item.symbol}
                    </span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {item.exchange}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-foreground/90 max-w-[200px] truncate">
                    {item.company_name || "-"}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums">
                    <span
                      className={
                        item.net_profit && item.net_profit > 0
                          ? "text-green-500 dark:text-green-400"
                          : "text-red-500 dark:text-red-400"
                      }
                    >
                      {formatProfit(item.net_profit)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                    {formatProfit(item.revenue)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums">
                    <span
                      className={
                        item.profit_margin && item.profit_margin > 0
                          ? "text-green-500 dark:text-green-400"
                          : "text-red-500 dark:text-red-400"
                      }
                    >
                      {formatPercent(item.profit_margin)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                    {formatEps(item.eps)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/50 bg-muted/20">
          <span className="text-sm text-muted-foreground">
            {startIndex + 1}-{endIndex} of {totalItems}
          </span>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                Rows per page
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
                Page {currentPage}/{totalPages}
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

export function TopPerformersTableSkeleton({
  className,
}: {
  className?: string
}) {
  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex justify-between">
        <div className="h-4 w-48 rounded bg-muted animate-pulse" />
        <div className="h-8 w-8 rounded bg-muted animate-pulse" />
      </div>
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
        <div className="flex gap-4 pb-2 border-b border-border/30">
          <div className="h-4 w-8 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse" />
          <div className="h-4 w-40 rounded bg-muted animate-pulse" />
          <div className="h-4 w-24 rounded bg-muted animate-pulse ml-auto" />
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse" />
        </div>
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-8 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-40 rounded bg-muted animate-pulse" />
            <div className="h-4 w-24 rounded bg-muted animate-pulse ml-auto" />
            <div className="h-4 w-24 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
          </div>
        ))}
        <div className="flex justify-between pt-3 border-t border-border/30">
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          <div className="flex gap-2">
            <div className="h-8 w-24 rounded bg-muted animate-pulse" />
            <div className="h-8 w-24 rounded bg-muted animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  )
}
