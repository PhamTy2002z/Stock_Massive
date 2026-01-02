"use client"

import { memo } from "react"
import { Card } from "@/components/ui/card"
import { Sparkline } from "@/components/ui/sparkline"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown } from "lucide-react"

interface StockIndexCardProps {
  symbol: string
  name: string
  value: number
  change: number
  changePercent: number
  chartData?: number[]
  className?: string
}

export const StockIndexCard = memo(function StockIndexCard({
  name,
  value,
  change,
  changePercent,
  chartData = [],
  className,
}: StockIndexCardProps) {
  const isPositive = change >= 0

  // Format value with thousand separator
  const formattedValue = value.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  // Format change with sign
  const formattedChange = `${isPositive ? "+" : ""}${change.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`

  // Format percentage
  const formattedPercent = `${isPositive ? "+" : ""}${changePercent.toFixed(2)}%`

  return (
    <Card className={cn("p-5 hover:shadow-md transition-shadow cursor-pointer", className)}>
      <div className="flex items-start justify-between gap-4">
        {/* Left: Index info */}
        <div className="flex-1 min-w-0">
          {/* Index name */}
          <p className="text-sm font-medium text-muted-foreground truncate">
            {name}
          </p>

          {/* Value */}
          <p className="text-2xl font-semibold text-foreground mt-1 tabular-nums">
            {formattedValue}
          </p>

          {/* Change */}
          <div className="flex items-center gap-1.5 mt-1">
            {isPositive ? (
              <TrendingUp className="h-3.5 w-3.5 text-green-500 dark:text-green-400" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5 text-red-500 dark:text-red-400" />
            )}
            <span
              className={cn(
                "text-sm font-medium tabular-nums",
                isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"
              )}
            >
              {formattedChange}
            </span>
            <span
              className={cn(
                "text-sm font-medium tabular-nums",
                isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"
              )}
            >
              ({formattedPercent})
            </span>
          </div>
        </div>

        {/* Right: Sparkline chart */}
        {chartData.length > 1 && (
          <div className="flex-shrink-0">
            <Sparkline
              data={chartData}
              width={80}
              height={40}
              positive={isPositive}
            />
          </div>
        )}
      </div>
    </Card>
  )
})

export function StockIndexCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="h-4 w-20 rounded bg-muted animate-pulse" />
          <div className="h-7 w-28 rounded bg-muted animate-pulse mt-2" />
          <div className="flex items-center gap-1.5 mt-2">
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-14 rounded bg-muted animate-pulse" />
          </div>
        </div>
        <div className="h-10 w-20 rounded bg-muted animate-pulse" />
      </div>
    </Card>
  )
}
