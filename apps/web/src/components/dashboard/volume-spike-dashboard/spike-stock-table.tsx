"use client"

import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { formatPercent } from "@/lib/format"
import { signalIssueSentence } from "@/lib/signal-issues"
import {
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Info,
} from "lucide-react"
import type { VolumeSpikeItem } from "@/lib/api"
import { formatVolume, formatRatio, ratioColor } from "./shared"
import type { useSortedPagedRows, SpikeSortField } from "./use-sorted-paged-rows"

export type SpikeTableState = ReturnType<
  typeof useSortedPagedRows<VolumeSpikeItem>
>

/**
 * The spiking symbols, sortable and paginated.
 *
 * A row carries its own issues. A symbol whose baseline includes sessions it
 * did not trade is still a real spike, but the ratio behind it was drawn from a
 * quieter stretch than the others — so the row says so rather than sitting in
 * the list looking identical to the rest.
 */
export function SpikeStockTable({
  table,
  className,
}: {
  table: SpikeTableState
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
    return sortDir === "desc" ? (
      <ArrowDown className="h-3 w-3" />
    ) : (
      <ArrowUp className="h-3 w-3" />
    )
  }

  const handleRowClick = (symbol: string) => {
    router.push(`/analytics/deep-dive?symbol=${encodeURIComponent(symbol)}`)
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card overflow-hidden",
        className,
      )}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse min-w-[700px]">
          <thead>
            <tr className="border-b border-border bg-surface-sunken">
              <th className="py-2 px-3 text-center text-xs font-medium text-muted-foreground w-12">
                #
              </th>
              <th className="py-2 px-3 text-left text-xs font-medium text-muted-foreground">
                Mã
              </th>
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                <button
                  onClick={() => toggleSort("volume")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  KL <SortIcon field="volume" />
                </button>
              </th>
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                KL TB 20 phiên
              </th>
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                <button
                  onClick={() => toggleSort("ratio")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Tỷ lệ <SortIcon field="ratio" />
                </button>
              </th>
              <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                <button
                  onClick={() => toggleSort("change_pct")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Giá <SortIcon field="change_pct" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((stock, idx) => {
              const rank = (page - 1) * pageSize + idx + 1
              const notes = stock.issues.map(signalIssueSentence)
              return (
                <tr
                  key={stock.symbol}
                  onClick={() => handleRowClick(stock.symbol)}
                  onKeyDown={(e) => e.key === "Enter" && handleRowClick(stock.symbol)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Xem chi tiết ${stock.symbol}`}
                  className="border-b border-border hover:bg-foreground/[0.06] transition-colors cursor-pointer focus:outline-none focus:bg-surface-sunken"
                >
                  <td className="py-2 px-3 text-center text-xs text-muted-foreground tabular-nums">
                    {rank}
                  </td>
                  <td className="py-2 px-3">
                    <span className="text-sm font-semibold text-primary">
                      {stock.symbol}
                    </span>
                    {stock.exchange && (
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        {stock.exchange}
                      </span>
                    )}
                    {notes.length > 0 && (
                      <span
                        className="ml-2 inline-flex items-center gap-1 text-xs text-caution"
                        title={notes.join(" • ")}
                      >
                        <Info className="h-3 w-3" />
                        {notes[0]}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-sm text-right tabular-nums">
                    {formatVolume(stock.volume)}
                  </td>
                  <td className="py-2 px-3 text-sm text-right tabular-nums text-muted-foreground">
                    {formatVolume(stock.baseline_average_volume)}
                  </td>
                  <td className="py-2 px-3 text-sm text-right tabular-nums font-medium">
                    <span className={ratioColor(stock.ratio)}>
                      {formatRatio(stock.ratio)}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-sm text-right tabular-nums">
                    <span
                      className={
                        stock.change_pct && stock.change_pct >= 0
                          ? "text-positive"
                          : "text-negative"
                      }
                    >
                      {formatPercent(stock.change_pct)}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-surface-sunken">
          <span className="text-xs text-muted-foreground">
            {(page - 1) * pageSize + 1}-
            {Math.min(page * pageSize, sortedRows.length)} / {sortedRows.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1 rounded hover:bg-muted disabled:opacity-50"
              aria-label="Trang trước"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs px-2">
              {page}/{totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1 rounded hover:bg-muted disabled:opacity-50"
              aria-label="Trang sau"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
