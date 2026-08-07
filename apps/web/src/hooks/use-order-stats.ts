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
    // These endpoints answer 501 when the data provider has no such capability
    // (vnstock 4.x dropped several). That is a permanent, per-feature answer —
    // not a page-level failure — so handle it in the component and don't retry.
    throwOnError: false,
    retry: false,
  })
}
