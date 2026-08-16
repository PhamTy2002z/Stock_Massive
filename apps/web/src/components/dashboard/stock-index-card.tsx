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

  const trendClass = isPositive ? "text-positive" : "text-negative"

  return (
    <Card
      className={cn(
        "rounded-card p-[14px] cursor-pointer",
        className
      )}
    >
      <p className="truncate text-micro font-semibold uppercase tracking-[0.07em] text-ink-5">
        {name}
      </p>

      <p className="mt-1.5 font-mono text-[1.34rem] font-semibold leading-[1.2] tracking-[-0.025em] text-foreground tabular-nums">
        {formattedValue}
      </p>

      <div
        className={cn(
          "mt-1 flex items-center gap-1.5 font-mono text-meta tabular-nums",
          trendClass
        )}
      >
        {isPositive ? (
          <TrendingUp className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        ) : (
          <TrendingDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        )}
        <span>
          {formattedChange} ({formattedPercent})
        </span>
      </div>

      {chartData.length > 1 && (
        <Sparkline
          data={chartData}
          width={200}
          height={40}
          positive={isPositive}
          stretch
          className="mt-3.5 block h-[30px] w-full"
        />
      )}
    </Card>
  )
})

export function StockIndexCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("rounded-card p-[14px]", className)}>
      <div className="h-4 w-20 rounded bg-muted animate-pulse" />
      <div className="mt-2 h-8 w-32 rounded bg-muted animate-pulse" />
      <div className="mt-1.5 h-5 w-28 rounded bg-muted animate-pulse" />
      <div className="mt-3.5 h-[30px] w-full rounded bg-muted animate-pulse" />
    </Card>
  )
}
