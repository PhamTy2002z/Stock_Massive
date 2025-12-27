"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchOrderStats, type OrderStatsItem } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useOrderStats(symbol: string | null, days: number = 30) {
  return useQuery<OrderStatsItem[]>({
    queryKey: symbol ? queryKeys.orderStats(symbol, days) : ["orderStats", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchOrderStats(symbol, days)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  })
}
