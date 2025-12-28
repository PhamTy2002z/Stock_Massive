"use client"

import { StockIndexCard } from "./stock-index-card"
import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMarketIndices } from "@/hooks/use-market-indices"

interface MarketIndicesProps {
  className?: string
}

export function MarketIndices({ className }: MarketIndicesProps) {
  // data is ALWAYS defined with useSuspenseQuery - Suspense handles loading, ErrorBoundary handles errors
  const { data: indices, isFetching, refetch } = useMarketIndices()

  return (
    <div className={className}>
      {/* Header with title and refresh button */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground">Chỉ số thị trường</h2>
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
      <MarketIndicesContent indices={indices} />
    </div>
  )
}

interface MarketIndicesContentProps {
  indices: NonNullable<ReturnType<typeof useMarketIndices>["data"]>
}

function MarketIndicesContent({ indices }: MarketIndicesContentProps) {
  if (indices.length === 0) {
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
