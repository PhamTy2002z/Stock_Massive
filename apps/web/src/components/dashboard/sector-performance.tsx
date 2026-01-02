"use client"

import { useSectorPerformance } from "@/hooks/use-sector-performance"
import { Skeleton } from "@/components/ui/skeleton"
import { RefreshCw, TrendingUp, TrendingDown } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Wrapper component with title and refresh button
 */
export function SectorPerformanceSection({ className }: { className?: string }) {
  const { data, isPending, isFetching, isPlaceholderData, refetch } = useSectorPerformance()

  // First load - show skeleton
  if (isPending) {
    return (
      <div className={className}>
        <div className="flex items-center justify-between mb-4">
          <div className="h-6 w-32 rounded bg-muted animate-pulse" />
          <div className="h-8 w-8 rounded bg-muted animate-pulse" />
        </div>
        <SectorPerformanceSkeleton />
      </div>
    )
  }

  return (
    <div className={className}>
      {/* Header with title and refresh button */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground">Hiệu suất ngành</h2>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
          title="Làm mới dữ liệu"
          aria-label="Làm mới dữ liệu"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>
      <div className="relative">
        <div className={cn(
          "transition-opacity duration-200",
          isPlaceholderData && "opacity-60"
        )}>
          <SectorPerformanceContent data={data} />
        </div>
        {isFetching && !isPending && (
          <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm rounded-full p-1.5">
            <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>
    </div>
  )
}

interface SectorPerformanceContentProps {
  data: ReturnType<typeof useSectorPerformance>["data"]
}

/**
 * Internal content component - renders the two cards
 */
function SectorPerformanceContent({ data }: SectorPerformanceContentProps) {
  if (!data || data.sectors.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">Không có dữ liệu ngành</p>
      </div>
    )
  }

  // Top 5 gainers: only positive change_pct, Top 5 losers: only negative change_pct
  const sortedSectors = [...data.sectors].sort((a, b) => b.change_pct - a.change_pct)
  const topGainers = sortedSectors.filter(s => s.change_pct > 0).slice(0, 5)
  const topLosers = sortedSectors.filter(s => s.change_pct < 0).sort((a, b) => a.change_pct - b.change_pct).slice(0, 5)

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Top 5 Gainers */}
      <div className="rounded-xl border bg-card">
        <div className="flex items-center gap-2 p-4 border-b">
          <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
          <h3 className="font-semibold">
            Top 5 ngành tăng
            <span className="text-muted-foreground font-normal text-sm ml-1">
              (Phiên {formatSessionDate(data.generated_at)})
            </span>
          </h3>
        </div>
        <div className="divide-y">
          {topGainers.length > 0 ? (
            topGainers.map((sector, index) => (
              <SectorRow key={sector.icb_code} sector={sector} rank={index + 1} type="gainer" />
            ))
          ) : (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Không có ngành tăng trong phiên
            </div>
          )}
        </div>
      </div>

      {/* Top 5 Losers */}
      <div className="rounded-xl border bg-card">
        <div className="flex items-center gap-2 p-4 border-b">
          <TrendingDown className="h-5 w-5 text-red-600 dark:text-red-400" />
          <h3 className="font-semibold">
            Top 5 ngành giảm
            <span className="text-muted-foreground font-normal text-sm ml-1">
              (Phiên {formatSessionDate(data.generated_at)})
            </span>
          </h3>
        </div>
        <div className="divide-y">
          {topLosers.length > 0 ? (
            topLosers.map((sector, index) => (
              <SectorRow key={sector.icb_code} sector={sector} rank={index + 1} type="loser" />
            ))
          ) : (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Không có ngành giảm trong phiên
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

interface SectorRowProps {
  sector: {
    icb_code: string
    icb_name: string
    change_pct: number
    total_market_cap: number
    stock_count: number
    top_gainers: string[]
    top_losers: string[]
  }
  rank: number
  type: "gainer" | "loser"
}

function SectorRow({ sector, rank, type }: SectorRowProps) {
  // Color based on actual change_pct value, not type
  const isPositive = sector.change_pct >= 0
  const colorClass = isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
  // Rank badge color based on list type (gainer list = green, loser list = red)
  const isGainerList = type === "gainer"
  const bgClass = isGainerList ? "bg-green-500/10 dark:bg-green-400/10" : "bg-red-500/10 dark:bg-red-400/10"
  const rankColorClass = isGainerList ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"

  return (
    <div className="flex items-center gap-3 p-3 hover:bg-muted/30 transition-colors">
      {/* Rank */}
      <div
        className={cn(
          "flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold",
          bgClass,
          rankColorClass
        )}
      >
        {rank}
      </div>

      {/* Sector Info */}
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{sector.icb_name}</div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatMarketCap(sector.total_market_cap)}</span>
          <span>•</span>
          <span>{sector.stock_count} CP</span>
        </div>
      </div>

      {/* Change Percent */}
      <div className={cn("flex-shrink-0 text-right", colorClass)}>
        <div className="flex items-center gap-1 font-semibold tabular-nums">
          {isPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
          <span>
            {isPositive ? "+" : ""}
            {sector.change_pct.toFixed(2)}%
          </span>
        </div>
        {/* Top stocks in sector */}
        <div className="text-xs mt-0.5">
          {isGainerList
            ? sector.top_gainers.slice(0, 2).join(", ")
            : sector.top_losers.slice(0, 2).join(", ")}
        </div>
      </div>
    </div>
  )
}

function SectorPerformanceSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Skeleton for gainers */}
      <div className="rounded-xl border bg-card">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-5 rounded-full" />
            <Skeleton className="h-5 w-32" />
          </div>
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="divide-y">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-3 p-3">
              <Skeleton className="h-7 w-7 rounded-full" />
              <div className="flex-1">
                <Skeleton className="h-4 w-32 mb-1" />
                <Skeleton className="h-3 w-20" />
              </div>
              <div className="text-right">
                <Skeleton className="h-4 w-16 mb-1" />
                <Skeleton className="h-3 w-12" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Skeleton for losers */}
      <div className="rounded-xl border bg-card">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-5 rounded-full" />
            <Skeleton className="h-5 w-32" />
          </div>
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="divide-y">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-3 p-3">
              <Skeleton className="h-7 w-7 rounded-full" />
              <div className="flex-1">
                <Skeleton className="h-4 w-32 mb-1" />
                <Skeleton className="h-3 w-20" />
              </div>
              <div className="text-right">
                <Skeleton className="h-4 w-16 mb-1" />
                <Skeleton className="h-3 w-12" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function formatMarketCap(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}T tỷ`
  }
  if (value >= 1) {
    return `${value.toFixed(0)} tỷ`
  }
  return `${(value * 1000).toFixed(0)} triệu`
}

function formatSessionDate(dateStr: string): string {
  const date = new Date(dateStr)
  const day = date.getDate().toString().padStart(2, "0")
  const month = (date.getMonth() + 1).toString().padStart(2, "0")
  const year = date.getFullYear()
  return `${day}/${month}/${year}`
}

export { SectorPerformanceSkeleton }
