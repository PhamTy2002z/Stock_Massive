"use client"

import { StockIndexCard } from "./stock-index-card"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMarketIndices } from "@/hooks/use-market-indices"

interface MarketIndicesProps {
  className?: string
}

export function MarketIndices({ className }: MarketIndicesProps) {
  const { data: indices, isLoading, isFetching, error, refetch } = useMarketIndices()

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
      <MarketIndicesContent
        indices={indices ?? []}
        isLoading={isLoading}
        error={error}
        refetch={refetch}
      />
    </div>
  )
}

interface MarketIndicesContentProps {
  indices: NonNullable<ReturnType<typeof useMarketIndices>["data"]>
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

function MarketIndicesContent({ indices, isLoading, error, refetch }: MarketIndicesContentProps) {
  if (isLoading && indices.length === 0) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <MarketIndexSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm text-muted-foreground mb-3">{error.message}</p>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          <RefreshCw className="h-4 w-4" />
          Thử lại
        </button>
      </div>
    )
  }

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

function MarketIndexSkeleton() {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-24" />
        </div>
        <Skeleton className="h-10 w-20" />
      </div>
    </div>
  )
}
