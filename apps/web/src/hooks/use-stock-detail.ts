"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchStockDetail, type StockDetail } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for stock detail - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useStockDetail(symbol: string) {
  const { data, isFetching, refetch } = useSuspenseQuery<StockDetail>({
    queryKey: queryKeys.stockDetail(symbol),
    queryFn: () => fetchStockDetail(symbol),
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
    refetchIntervalInBackground: false,
  })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}

// Utility for validating symbol format
export const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/
export const isValidSymbol = (symbol: string | null): symbol is string =>
  !!symbol && SYMBOL_PATTERN.test(symbol)
