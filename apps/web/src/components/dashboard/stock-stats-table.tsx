"use client"

import { cn } from "@/lib/utils"

interface StockStatsTableProps {
  // Column 1: Price info
  openPrice: number // Mở cửa
  highPrice: number // Cao nhất
  lowPrice: number // Thấp nhất
  tradingVolume: number // KLGD (shares)

  // Column 2: 52-week & market cap
  marketCap: number // Vốn hoá (billion VND)
  high52Week: number // Cao 52T
  low52Week: number // Thấp 52T
  avgVolume52Week: number // KLBQ 52T (shares)

  // Column 3: Fundamentals
  eps: number | null // EPS
  pe: number | null // P/E
  pb: number | null // P/B (Price-to-Book)
  dividendYield: number | null // Tỷ suất cổ tức (%)

  className?: string
}

// Format number with Vietnamese locale
function formatNumber(value: number | null, decimals = 2): string {
  if (value === null || value === undefined) return "N/A"
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

// Format market cap (trillion VND)
function formatMarketCap(value: number): string {
  if (value >= 1000) {
    return `${formatNumber(value / 1000, 1)} nghìn tỷ`
  }
  return `${formatNumber(value, 1)} tỷ`
}

// Format volume (millions)
function formatVolume(value: number): string {
  if (value >= 1000000) {
    return `${formatNumber(value / 1000000, 1)} triệu`
  }
  if (value >= 1000) {
    return `${formatNumber(value / 1000, 1)} nghìn`
  }
  return formatNumber(value, 0)
}

export function StockStatsTable({
  openPrice,
  highPrice,
  lowPrice,
  tradingVolume,
  marketCap,
  high52Week,
  low52Week,
  avgVolume52Week,
  eps,
  pe,
  pb,
  dividendYield,
  className,
}: StockStatsTableProps) {
  return (
    <div className={cn("rounded-lg border bg-card overflow-hidden", className)}>
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border">
        {/* Column 1: Price Info */}
        <div className="divide-y divide-border">
          <StatsRow label="Mở cửa" value={formatNumber(openPrice)} />
          <StatsRow label="Cao nhất" value={formatNumber(highPrice)} />
          <StatsRow label="Thấp nhất" value={formatNumber(lowPrice)} />
          <StatsRow label="KLGD" value={formatVolume(tradingVolume)} />
        </div>

        {/* Column 2: 52-Week & Market Cap */}
        <div className="divide-y divide-border">
          <StatsRow label="Vốn hoá" value={formatMarketCap(marketCap)} />
          <StatsRow label="Cao 52T" value={formatNumber(high52Week)} />
          <StatsRow label="Thấp 52T" value={formatNumber(low52Week)} />
          <StatsRow label="KLBQ 52T" value={formatVolume(avgVolume52Week)} />
        </div>

        {/* Column 3: Fundamentals */}
        <div className="divide-y divide-border">
          <StatsRow label="EPS" value={eps !== null ? formatNumber(eps, 0) : "N/A"} />
          <StatsRow label="P/E" value={pe !== null ? formatNumber(pe, 2) : "N/A"} />
          <StatsRow label="P/B" value={pb !== null ? formatNumber(pb, 2) : "N/A"} />
          <StatsRow label="Tỷ suất cổ tức" value={dividendYield !== null ? `${formatNumber(dividendYield, 1)}%` : "N/A"} />
        </div>
      </div>
    </div>
  )
}

// Stats Row Component
function StatsRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-5 py-3.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium tabular-nums text-foreground text-right">{value}</span>
    </div>
  )
}
