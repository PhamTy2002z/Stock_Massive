"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchStockDetail, type StockDetail } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/

interface UseStockDetailResult {
  data: StockDetail | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export function useStockDetail(symbol: string | null): UseStockDetailResult {
  const isValidSymbol = !!symbol && SYMBOL_PATTERN.test(symbol)

  const query = useQuery({
    queryKey: symbol ? queryKeys.stockDetail(symbol) : ["stock", "empty"],
    queryFn: async () => {
      if (!symbol || !isValidSymbol) {
        throw new Error("Invalid stock symbol format")
      }
      return fetchStockDetail(symbol)
    },
    enabled: isValidSymbol,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
    refetchIntervalInBackground: true, // Keep refreshing even when tab is not focused
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  }
}
