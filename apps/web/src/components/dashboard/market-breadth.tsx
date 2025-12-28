"use client"

import { useMarketOverview } from "@/hooks/use-market-overview"
import { Card, CardContent } from "@/components/ui/card"

export function MarketBreadth() {
  const { data } = useMarketOverview()
  const { advances, declines, unchanged, total } = data.market_breadth

  const advancesPct = total > 0 ? (advances / total) * 100 : 0
  const declinesPct = total > 0 ? (declines / total) * 100 : 0
  const unchangedPct = total > 0 ? (unchanged / total) * 100 : 0

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-center justify-between mb-3 text-sm">
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-green-500" />
            Tang: {advances} ({advancesPct.toFixed(1)}%)
          </span>
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-500" />
            Giam: {declines} ({declinesPct.toFixed(1)}%)
          </span>
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-gray-400" />
            Dung gia: {unchanged}
          </span>
        </div>
        <div className="h-3 flex rounded-full overflow-hidden bg-muted">
          <div
            className="bg-green-500 transition-all duration-300"
            style={{ width: `${advancesPct}%` }}
          />
          <div
            className="bg-gray-400 transition-all duration-300"
            style={{ width: `${unchangedPct}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-300"
            style={{ width: `${declinesPct}%` }}
          />
        </div>
      </CardContent>
    </Card>
  )
}
