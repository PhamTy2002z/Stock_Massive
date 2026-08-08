"use client"

import { Trophy } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { SpikeStockTable, type SpikeStock } from "./spike-stock-table"
import { useSortedPagedRows } from "./use-sorted-paged-rows"

// Top Volatility Stocks Table Component
export function TopVolatilityTable({ stocks }: { stocks: SpikeStock[] }) {
  const table = useSortedPagedRows(stocks)

  if (stocks.length === 0) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Trophy className="h-5 w-5 text-yellow-500" />
        <h2 className="text-lg font-semibold">Xếp hạng biến động</h2>
        <Badge variant="secondary" className="text-xs">
          {stocks.length} CP
        </Badge>
      </div>
      <SpikeStockTable table={table} showRank />
    </div>
  )
}
