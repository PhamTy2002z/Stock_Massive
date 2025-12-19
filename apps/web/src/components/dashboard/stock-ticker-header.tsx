"use client"

import { useEffect, useRef, useState } from "react"
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
  const [priceFlash, setPriceFlash] = useState(false)
  const prevPriceRef = useRef(price)
  const isPositive = change >= 0

  // Trigger flash animation when price changes
  useEffect(() => {
    if (price !== prevPriceRef.current && prevPriceRef.current !== 0) {
      setPriceFlash(true)
      const timer = setTimeout(() => setPriceFlash(false), 500)
      prevPriceRef.current = price
      return () => clearTimeout(timer)
    }
    prevPriceRef.current = price
  }, [price])

  // Format with comma as decimal separator (Vietnamese style)
  const formattedPrice = price.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  const formattedChange = change.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  const formattedPercent = `${isPositive ? "+" : ""}${changePercent.toFixed(2).replace(".", ",")}%`

  return (
    <div className={cn("py-4", className)}>
      <div className="flex items-center justify-between gap-4">
        {/* Left: Symbol | Company Name */}
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-foreground">
              {symbol}
            </span>
            <span className="text-muted-foreground/60">|</span>
            <span className="text-base text-muted-foreground truncate">
              {companyName}
            </span>
          </div>
        </div>

        {/* Right: Price & Change */}
        <div className="text-right shrink-0">
          <p
            className={cn(
              "text-2xl font-semibold tabular-nums transition-all duration-300",
              isPositive ? "text-emerald-500 dark:text-emerald-400" : "text-red-500 dark:text-red-400",
              priceFlash && "scale-110 brightness-125"
            )}
          >
            {formattedPrice}
          </p>
          <p
            className={cn(
              "text-sm font-medium tabular-nums",
              isPositive ? "text-emerald-500 dark:text-emerald-400" : "text-red-500 dark:text-red-400"
            )}
          >
            ({formattedPercent}) {isPositive ? "+" : ""}{formattedChange}
          </p>
        </div>
      </div>
    </div>
  )
}
