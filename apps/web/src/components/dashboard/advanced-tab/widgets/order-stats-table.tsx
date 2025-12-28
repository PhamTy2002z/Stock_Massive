"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { OrderStatsItem } from "@/lib/api"
import { TrendingUp, TrendingDown, Minus, Calendar } from "lucide-react"

interface OrderStatsTableProps {
  data: OrderStatsItem[] | undefined
  isLoading: boolean
}

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN")
}

function formatVolume(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })
}

function formatWeekday(dateStr: string): string {
  const date = new Date(dateStr)
  const weekdays = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]
  return weekdays[date.getDay()]
}

export function OrderStatsTable({ data, isLoading }: OrderStatsTableProps) {
  if (isLoading) {
    return <OrderStatsTableSkeleton />
  }

  if (!data || !Array.isArray(data) || data.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-muted/30 flex items-center justify-center">
          <Calendar className="w-8 h-8 text-muted-foreground/40" />
        </div>
        <p className="text-sm font-medium text-muted-foreground">Dữ liệu order stats chưa khả dụng</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Tính năng đang được phát triển</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border/50 overflow-hidden bg-card/50">
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/40 border-b border-border/50">
              <th className="text-xs text-left font-semibold text-muted-foreground py-3 px-4 whitespace-nowrap">
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" />
                  Ngày
                </span>
              </th>
              <th className="text-xs text-right font-semibold text-muted-foreground py-3 px-4 whitespace-nowrap">
                <span className="text-green-600 dark:text-green-500">Lệnh Mua</span>
              </th>
              <th className="text-xs text-right font-semibold text-muted-foreground py-3 px-4 whitespace-nowrap">
                <span className="text-red-600 dark:text-red-500">Lệnh Bán</span>
              </th>
              <th className="text-xs text-right font-semibold text-muted-foreground py-3 px-4 whitespace-nowrap">
                KL Mua
              </th>
              <th className="text-xs text-right font-semibold text-muted-foreground py-3 px-4 whitespace-nowrap">
                KL Bán
              </th>
              <th className="text-xs text-right font-semibold text-muted-foreground py-3 px-4 whitespace-nowrap">
                Chênh lệch
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => {
              const netVolume = row.buy_volume - row.sell_volume
              const isPositive = netVolume > 0
              const isNegative = netVolume < 0

              return (
                <tr
                  key={row.date}
                  className={cn(
                    "border-b border-border/30 transition-all duration-150",
                    "hover:bg-muted/30 cursor-pointer",
                    "group"
                  )}
                >
                  {/* Date */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "text-[10px] font-medium px-1.5 py-0.5 rounded",
                          index === 0 ? "bg-primary/10 text-primary" : "bg-muted/50 text-muted-foreground"
                        )}
                      >
                        {formatWeekday(row.date)}
                      </span>
                      <span className="text-sm font-medium tabular-nums">
                        {formatDate(row.date)}
                      </span>
                    </div>
                  </td>

                  {/* Buy Orders */}
                  <td className="text-sm text-right tabular-nums font-medium py-3 px-4">
                    <span className="text-green-600 dark:text-green-400 group-hover:font-semibold transition-all">
                      {formatNumber(row.buy_orders)}
                    </span>
                  </td>

                  {/* Sell Orders */}
                  <td className="text-sm text-right tabular-nums font-medium py-3 px-4">
                    <span className="text-red-600 dark:text-red-400 group-hover:font-semibold transition-all">
                      {formatNumber(row.sell_orders)}
                    </span>
                  </td>

                  {/* Buy Volume */}
                  <td className="text-sm text-right tabular-nums py-3 px-4">
                    <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                      {formatVolume(row.buy_volume)}
                    </span>
                  </td>

                  {/* Sell Volume */}
                  <td className="text-sm text-right tabular-nums py-3 px-4">
                    <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                      {formatVolume(row.sell_volume)}
                    </span>
                  </td>

                  {/* Net Volume */}
                  <td className="text-sm text-right py-3 px-4">
                    <div
                      className={cn(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-semibold tabular-nums",
                        isPositive && "bg-green-500/10 text-green-600 dark:text-green-400",
                        isNegative && "bg-red-500/10 text-red-600 dark:text-red-400",
                        !isPositive && !isNegative && "bg-muted/50 text-muted-foreground"
                      )}
                    >
                      {isPositive && <TrendingUp className="h-3 w-3" />}
                      {isNegative && <TrendingDown className="h-3 w-3" />}
                      {!isPositive && !isNegative && <Minus className="h-3 w-3" />}
                      <span>
                        {isPositive ? "+" : ""}
                        {formatVolume(netVolume)}
                      </span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Footer summary */}
      {data.length > 0 && (
        <div className="bg-muted/20 border-t border-border/50 px-4 py-2.5 flex items-center justify-between text-xs text-muted-foreground">
          <span>Hiển thị {data.length} phiên gần nhất</span>
          <span className="tabular-nums">
            TB: {formatVolume(
              data.reduce((sum, r) => sum + (r.buy_volume - r.sell_volume), 0) / data.length
            )} / phiên
          </span>
        </div>
      )}
    </div>
  )
}

function OrderStatsTableSkeleton() {
  return (
    <div className="rounded-xl border border-border/50 overflow-hidden">
      {/* Header */}
      <div className="bg-muted/40 p-3 border-b border-border/50">
        <div className="flex gap-4">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16 ml-auto" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>
      {/* Rows */}
      <div className="p-3 space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4 items-center">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-8 rounded" />
              <Skeleton className="h-4 w-12" />
            </div>
            <Skeleton className="h-4 w-16 ml-auto" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-6 w-20 rounded-md" />
          </div>
        ))}
      </div>
    </div>
  )
}

export { OrderStatsTableSkeleton }
