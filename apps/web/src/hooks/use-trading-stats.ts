"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchTradingStats, type TradingStatsResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useTradingStats(symbol: string | null) {
  return useQuery<TradingStatsResponse>({
    queryKey: symbol ? queryKeys.tradingStats(symbol) : ["tradingStats", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchTradingStats(symbol)
    },
    enabled: !!symbol,
    staleTime: 15 * 60 * 1000, // 15 minutes
    retry: 2,
  })
}
