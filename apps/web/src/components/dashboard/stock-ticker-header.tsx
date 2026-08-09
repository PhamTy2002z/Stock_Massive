"use client"

import { useEffect, useRef, useState } from "react"
import { Bell, RefreshCw, Star, TrendingDown, TrendingUp } from "lucide-react"
import { cn } from "@/lib/utils"

interface StockTickerHeaderProps {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  /** Limit prices for the session. Omitted when the feed has not supplied them. */
  ceiling?: number | null
  floor?: number | null
  refPrice?: number | null
  /** Wired to the detail query's refetch; the icon spins while it is in flight. */
  onRefresh?: () => void
  isRefreshing?: boolean
  className?: string
}

const priceFormat = new Intl.NumberFormat("vi-VN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Limit prices are whole đồng — decimals on them are noise, not precision. */
const limitFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 })

function LimitPrice({
  label,
  value,
  className,
}: {
  label: string
  value: number | null | undefined
  className: string
}) {
  if (value === null || value === undefined) return null

  return (
    <span className="font-normal text-muted-foreground">
      {label}{" "}
      <span className={cn("font-semibold", className)}>{limitFormat.format(value)}</span>
    </span>
  )
}

export function StockTickerHeader({
  symbol,
  companyName,
  price,
  change,
  changePercent,
  ceiling,
  floor,
  refPrice,
  onRefresh,
  isRefreshing = false,
  className,
}: StockTickerHeaderProps) {
  const [priceFlash, setPriceFlash] = useState(false)
  const prevPriceRef = useRef(price)
  const isPositive = change >= 0
  const Trend = isPositive ? TrendingUp : TrendingDown
  const toneClass = isPositive ? "text-positive" : "text-negative"

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

  const formattedPrice = priceFormat.format(price)
  const formattedChange = `${isPositive ? "+" : ""}${priceFormat.format(change)}`
  const formattedPercent = `${isPositive ? "+" : ""}${changePercent.toFixed(2).replace(".", ",")}%`

  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-6 py-4", className)}>
      {/* Identity: ticker leads, company name is support text, limits sit under both */}
      <div className="flex min-w-0 flex-col gap-2.5">
        <div className="flex min-w-0 items-baseline gap-3">
          <span className="text-[30px] font-semibold leading-[1.1] tracking-[-0.6px]">
            {symbol}
          </span>
          <span aria-hidden className="h-5 w-px shrink-0 bg-border" />
          <span className="truncate text-[17px] leading-[1.47] tracking-[-0.374px] text-foreground/80">
            {companyName}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3.5 text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] tabular-nums">
          {/* Ceiling purple / reference yellow / floor cyan — the board colours
              Vietnamese traders already read, kept off the up-down green-red. */}
          <LimitPrice label="Trần" value={ceiling} className="text-[#7c3fae]" />
          <LimitPrice label="TC" value={refPrice} className="text-[#7a5c00]" />
          <LimitPrice label="Sàn" value={floor} className="text-[#06607f]" />
        </div>
      </div>

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex flex-col items-end gap-0.5">
          <span
            className={cn(
              "text-[40px] font-semibold leading-none tracking-[-0.8px] tabular-nums transition-all duration-300",
              toneClass,
              priceFlash && "scale-105 brightness-110"
            )}
          >
            {formattedPrice}
          </span>
          <span
            className={cn(
              "flex items-center gap-1.5 text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums",
              toneClass
            )}
          >
            <Trend aria-hidden className="size-3.5" />
            {formattedChange} ({formattedPercent})
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Watchlist and price alerts have no endpoint yet, so they are shown
              as unavailable rather than faked with local-only state. */}
          <button
            type="button"
            disabled
            title="Danh mục theo dõi đang chờ API"
            className="flex items-center gap-[7px] rounded-full border border-border bg-card px-[15px] py-2 text-[13px] leading-[1.29] tracking-[-0.208px] disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Star aria-hidden className="size-3.5" />
            Theo dõi
          </button>
          <button
            type="button"
            disabled
            title="Cảnh báo giá đang chờ API"
            className="flex items-center gap-[7px] rounded-full border border-border bg-card px-[15px] py-2 text-[13px] leading-[1.29] tracking-[-0.208px] disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Bell aria-hidden className="size-3.5" />
            Cảnh báo giá
          </button>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={isRefreshing}
              title="Làm mới"
              className="flex size-9 items-center justify-center rounded-full text-interactive transition-[background-color,transform] duration-150 hover:bg-muted active:scale-95 disabled:cursor-progress"
            >
              <RefreshCw aria-hidden className={cn("size-4", isRefreshing && "animate-spin")} />
              <span className="sr-only">Làm mới dữ liệu {symbol}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
