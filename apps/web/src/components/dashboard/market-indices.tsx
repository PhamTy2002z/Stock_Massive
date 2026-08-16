"use client"

import { StockIndexCard, StockIndexCardSkeleton } from "./stock-index-card"
import { RefreshButton, SectionHeader } from "./ui-kit"
import { cn } from "@/lib/utils"
import { useMarketIndices } from "@/hooks/use-market-indices"

interface MarketIndicesProps {
  className?: string
}

export function MarketIndices({ className }: MarketIndicesProps) {
  const { data: indices, isPending, isFetching, isPlaceholderData, dataUpdatedAt, refetch } =
    useMarketIndices()

  // First load - show skeleton
  if (isPending) {
    return <MarketIndicesSkeleton className={className} />
  }

  // When the board last answered, not when the page rendered — the difference
  // matters on a market page that keeps polling.
  const updated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : null

  return (
    <section className={cn("min-w-0", className)}>
      <SectionHeader title="Chỉ số thị trường">
        {updated && (
          <span className="text-[13px] leading-[1.43] tracking-[-0.224px] text-muted-foreground">
            {updated.replace(", ", " · ")}
          </span>
        )}
        <RefreshButton
          onClick={() => void refetch()}
          isRefreshing={isFetching}
          label="chỉ số thị trường"
        />
      </SectionHeader>

      {/* Stale figures dim while the next answer is in flight, so a number
          nobody has confirmed yet never looks freshly delivered. */}
      <div className={cn("transition-opacity duration-200", isPlaceholderData && "opacity-60")}>
        <MarketIndicesContent indices={indices} />
      </div>
    </section>
  )
}

interface MarketIndicesContentProps {
  indices: ReturnType<typeof useMarketIndices>["data"]
}

function MarketIndicesContent({ indices }: MarketIndicesContentProps) {
  if (!indices || indices.length === 0) {
    return (
      <div className="rounded-card border border-border bg-card p-6 text-center">
        <p className="text-[15px] leading-[1.47] tracking-[-0.374px] text-muted-foreground">
          Không có dữ liệu chỉ số
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5">
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
      <div className="mb-3.5 flex items-center justify-between">
        <div className="h-8 w-44 animate-pulse rounded bg-muted" />
        <div className="size-9 animate-pulse rounded-full bg-muted" />
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5">
        {[...Array(4)].map((_, i) => (
          <StockIndexCardSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}
