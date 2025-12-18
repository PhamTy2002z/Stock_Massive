"use client"

import { useEffect, useState } from "react"
import { StockIndexCard } from "./stock-index-card"
import { Skeleton } from "@/components/ui/skeleton"
import { fetchMarketIndices, type MarketIndex } from "@/lib/api"
import { AlertCircle, RefreshCw } from "lucide-react"

interface MarketIndicesProps {
  className?: string
}

export function MarketIndices({ className }: MarketIndicesProps) {
  const [indices, setIndices] = useState<MarketIndex[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await fetchMarketIndices()
      setIndices(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load market data")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  if (isLoading) {
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
        <p className="text-sm text-muted-foreground mb-3">{error}</p>
        <button
          onClick={loadData}
          className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    )
  }

  if (indices.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">No market data available</p>
      </div>
    )
  }

  return (
    <div className={className}>
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
