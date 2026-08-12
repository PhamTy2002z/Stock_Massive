"use client"

import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { formatPercent } from "@/lib/format"
import {
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"
import {
  ANOMALY_COLORS,
  ANOMALY_BADGE_VARIANTS,
  formatVolume,
  formatRatio,
} from "./shared"
import type { useSortedPagedRows, SpikeSortField } from "./use-sorted-paged-rows"

export type SpikeStock = IndustryVolumeSpikeGroup["stocks"][number]

export type SpikeTableState = ReturnType<typeof useSortedPagedRows<SpikeStock>>

/**
 * Shared presentational sortable + paginated table of spiking stocks.
 * Sort/page state comes from `useSortedPagedRows`, owned by the caller so
 * state survives even if this table unmounts (e.g. collapsed sections).
 * `showRank` adds the rank (#) and industry columns used by the ranking table.
 */
export function SpikeStockTable({
  table,
  showRank = false,
  className,
}: {
  table: SpikeTableState
  showRank?: boolean
  className?: string
}) {
  const router = useRouter()
  const {
    sortField,
    sortDir,
    page,
    setPage,
    pageSize,
    sortedRows,
    pagedRows,
    totalPages,
    toggleSort,
  } = table

  const SortIcon = ({ field }: { field: SpikeSortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-50" />
    return sortDir === "desc" ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />
  }

  const handleRowClick = (symbol: string) => {
    router.push(`/analytics/deep-dive?symbol=${encodeURIComponent(symbol)}`)
  }

  return (
    <div className={cn("rounded-lg border border-border/50 bg-card/50 overflow-hidden", className)}>
      <div className="overflow-x-auto">
        <table className={cn("w-full border-collapse", showRank ? "min-w-[750px]" : "min-w-[700px]")}>
          <thead>
            <tr className="border-b border-border/50 bg-muted/30">
              {showRank && (
                <th className="py-2 px-3 text-center text-xs font-medium text-muted-foreground w-12">#</th>
              )}
              <th className="py-2 px-3 text-left text-xs font-medium text-muted-foreground">Mã</th>
              <th className="py-2 px-3 text-left text-xs font-medium text-muted-foreground">Công ty</th>
              {showRank && (
                <th className="py-2 px-3 text-left text-xs font-medium text-muted-foreground">Ngành</th>
              )}
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                <button onClick={() => toggleSort("current_volume")} className="inline-flex items-center gap-1 hover:text-foreground">
                  KL <SortIcon field="current_volume" />
                </button>
              </th>
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                <button onClick={() => toggleSort("spike_ratio")} className="inline-flex items-center gap-1 hover:text-foreground">
                  Tỷ lệ <SortIcon field="spike_ratio" />
                </button>
              </th>
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                <button onClick={() => toggleSort("price_change_pct")} className="inline-flex items-center gap-1 hover:text-foreground">
                  Giá <SortIcon field="price_change_pct" />
                </button>
              </th>
              <th className="py-2 px-3 text-center text-xs font-medium text-muted-foreground">Mức độ</th>
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((stock, idx) => {
              const rank = (page - 1) * pageSize + idx + 1
              return (
                <tr
                  key={stock.symbol}
                  onClick={() => handleRowClick(stock.symbol)}
                  onKeyDown={(e) => e.key === "Enter" && handleRowClick(stock.symbol)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Xem chi tiết ${stock.symbol}`}
                  className="border-b border-border/30 hover:bg-muted/20 transition-colors cursor-pointer focus:outline-none focus:bg-muted/30"
                >
                  {showRank && (
                    <td className="py-2 px-3 text-center">
                      <span className={cn(
                        "inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold",
                        rank === 1 && "bg-yellow-500/20 text-yellow-600 dark:text-yellow-400",
                        rank === 2 && "bg-muted-foreground/25 text-muted-foreground",
                        rank === 3 && "bg-foreground/15 text-foreground",
                        rank > 3 && "text-muted-foreground"
                      )}>
                        {rank}
                      </span>
                    </td>
                  )}
                  <td className="py-2 px-3">
                    <span className="text-sm font-semibold text-primary">{stock.symbol}</span>
                    <span className="ml-1.5 text-xs text-muted-foreground">{stock.exchange}</span>
                  </td>
                  <td className={cn(
                    "py-2 px-3 text-sm text-foreground/90 truncate",
                    showRank ? "max-w-[180px]" : "max-w-[200px]"
                  )}>
                    {stock.company_name || "-"}
                  </td>
                  {showRank && (
                    <td className="py-2 px-3 text-xs text-muted-foreground max-w-[120px] truncate">
                      {stock.icb_name || "-"}
                    </td>
                  )}
                  <td className="py-2 px-3 text-sm text-right tabular-nums">
                    {formatVolume(stock.current_volume)}
                  </td>
                  <td className="py-2 px-3 text-sm text-right tabular-nums font-medium">
                    <span style={{ color: ANOMALY_COLORS[stock.anomaly_level] }}>
                      {formatRatio(stock.spike_ratio)}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-sm text-right tabular-nums">
                    <span className={stock.price_change_pct && stock.price_change_pct >= 0 ? "text-green-500" : "text-red-500"}>
                      {formatPercent(stock.price_change_pct)}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <Badge variant={ANOMALY_BADGE_VARIANTS[stock.anomaly_level]} className="text-xs">
                      {stock.anomaly_level === "very_high" ? ">3x" : stock.anomaly_level === "high" ? "2-3x" : "1.5-2x"}
                    </Badge>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 border-t border-border/50 bg-muted/20">
          <span className="text-xs text-muted-foreground">
            {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, sortedRows.length)} / {sortedRows.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1 rounded hover:bg-muted disabled:opacity-50"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs px-2">{page}/{totalPages}</span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1 rounded hover:bg-muted disabled:opacity-50"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
