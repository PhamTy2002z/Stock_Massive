"use client"

import { cn } from "@/lib/utils"

interface StockTickerHeaderProps {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  className?: string
}

export function StockTickerHeader({
  symbol,
  companyName,
  price,
  change,
  changePercent,
  className,
}: StockTickerHeaderProps) {
  const isPositive = change >= 0

  // Format with comma as decimal separator (Vietnamese style)
  const formattedPrice = price.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).replace(".", ",")

  const formattedChange = change.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).replace(".", ",")

  const formattedPercent = `${isPositive ? "+" : ""}${changePercent.toFixed(2).replace(".", ",")}%`

  return (
    <div className={cn("py-4", className)}>
      <div className="flex items-start justify-between gap-4">
        {/* Left: Company Name & Symbol */}
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold text-foreground leading-tight">
            {companyName}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{symbol}</p>
        </div>

        {/* Right: Price & Change */}
        <div className="text-right shrink-0">
          <p className="text-2xl font-semibold tabular-nums text-emerald-500">
            {formattedPrice}
          </p>
          <p
            className={cn(
              "mt-1 text-sm font-medium tabular-nums",
              isPositive ? "text-emerald-500" : "text-red-500"
            )}
          >
            ({formattedPercent}) {isPositive ? "+" : ""}{formattedChange}
          </p>
        </div>
      </div>
    </div>
  )
}
