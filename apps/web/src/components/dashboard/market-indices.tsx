"use client"

import { StockIndexCard, StockIndexCardSkeleton } from "./stock-index-card"
import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMarketIndices } from "@/hooks/use-market-indices"

interface MarketIndicesProps {
  className?: string
}

export function MarketIndices({ className }: MarketIndicesProps) {
  const { data: indices, isPending, isFetching, isPlaceholderData, refetch } = useMarketIndices()

  // First load - show skeleton
  if (isPending) {
    return <MarketIndicesSkeleton className={className} />
  }

  return (
    <div className={className}>
      {/* Header with title and refresh button */}
      <div className="flex items-center justify-between gap-4 mb-3.5">
        <h2 className="text-2xl font-semibold leading-tight tracking-[-0.374px] text-foreground">
          Chỉ số thị trường
        </h2>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex h-9 w-9 items-center justify-center rounded-full text-interactive transition-colors hover:bg-accent active:scale-95 disabled:opacity-50"
          title="Làm mới dữ liệu"
          aria-label="Làm mới dữ liệu"
        >
          <RefreshCw className={cn("h-[18px] w-[18px]", isFetching && "animate-spin")} />
        </button>
      </div>
      <div className="relative">
        <div className={cn(
          "transition-opacity duration-200",
          isPlaceholderData && "opacity-60"
        )}>
          <MarketIndicesContent indices={indices} />
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

interface MarketIndicesContentProps {
  indices: ReturnType<typeof useMarketIndices>["data"]
}

function MarketIndicesContent({ indices }: MarketIndicesContentProps) {
  if (!indices || indices.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">Không có dữ liệu chỉ số</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {indices.map((index) => (
        <StockIndexCard
          key={index.symbol}
          symbol={index.symbol}
          name={index.name}
          value={index.value}
          change={index.change}
          changePercent={index.changePercent}
        />
      ))}
    </div>
  )
}

export function MarketIndicesSkeleton({ className }: { className?: string }) {
  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-3.5">
        <div className="h-7 w-44 rounded bg-muted animate-pulse" />
        <div className="h-9 w-9 rounded-full bg-muted animate-pulse" />
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5">
        {[...Array(4)].map((_, i) => (
          <StockIndexCardSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}
