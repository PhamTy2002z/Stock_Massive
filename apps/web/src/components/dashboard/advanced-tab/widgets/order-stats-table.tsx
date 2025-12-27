"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { OrderStatsItem } from "@/lib/api"

interface OrderStatsTableProps {
  data: OrderStatsItem[] | undefined
  isLoading: boolean
}

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN")
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })
}

export function OrderStatsTable({ data, isLoading }: OrderStatsTableProps) {
  if (isLoading) {
    return <OrderStatsTableSkeleton />
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Không có dữ liệu order stats
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/30 border-b border-border/50">
              <th className="text-xs text-left font-medium text-muted-foreground py-2.5 px-3">Ngày</th>
              <th className="text-xs text-right font-medium text-muted-foreground py-2.5 px-3">Lệnh Mua</th>
              <th className="text-xs text-right font-medium text-muted-foreground py-2.5 px-3">Lệnh Bán</th>
              <th className="text-xs text-right font-medium text-muted-foreground py-2.5 px-3">KL Mua</th>
              <th className="text-xs text-right font-medium text-muted-foreground py-2.5 px-3">KL Bán</th>
              <th className="text-xs text-right font-medium text-muted-foreground py-2.5 px-3">Chênh lệch</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => {
              const netVolume = row.buy_order_volume - row.sell_order_volume
              return (
                <tr key={row.date} className="border-b border-border/30 hover:bg-muted/20 transition-colors">
                  <td className="text-xs font-medium py-2 px-3">
                    {formatDate(row.date)}
                  </td>
                  <td className="text-xs text-right text-green-600 dark:text-green-400 py-2 px-3">
                    {formatNumber(row.buy_order_count)}
                  </td>
                  <td className="text-xs text-right text-red-600 dark:text-red-400 py-2 px-3">
                    {formatNumber(row.sell_order_count)}
                  </td>
                  <td className="text-xs text-right py-2 px-3">
                    {formatNumber(row.buy_order_volume)}
                  </td>
                  <td className="text-xs text-right py-2 px-3">
                    {formatNumber(row.sell_order_volume)}
                  </td>
                  <td
                    className={cn(
                      "text-xs text-right font-medium py-2 px-3",
                      netVolume > 0
                        ? "text-green-600 dark:text-green-400"
                        : netVolume < 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-muted-foreground"
                    )}
                  >
                    {netVolume > 0 ? "+" : ""}
                    {formatNumber(netVolume)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function OrderStatsTableSkeleton() {
  return (
    <div className="rounded-lg border border-border/50 p-4 space-y-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16 ml-auto" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  )
}

export { OrderStatsTableSkeleton }
