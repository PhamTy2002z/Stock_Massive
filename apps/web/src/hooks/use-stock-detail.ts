"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchStockDetail, type StockDetail } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/

interface UseStockDetailResult {
  data: StockDetail | null
  isLoading: boolean
  isFetching: boolean
  isPlaceholderData: boolean
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
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
