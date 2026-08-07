"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchForeignTrading, type ForeignTradingItem } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useForeignTrading(symbol: string | null, days: number = 30) {
  return useQuery<ForeignTradingItem[]>({
    queryKey: symbol ? queryKeys.foreignTrading(symbol, days) : ["foreignTrading", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchForeignTrading(symbol, days)
    },
    enabled: !!symbol,
    staleTime: 15 * 60 * 1000, // 15 minutes
    // These endpoints answer 501 when the data provider has no such capability
    // (vnstock 4.x dropped several). That is a permanent, per-feature answer —
    // not a page-level failure — so handle it in the component and don't retry.
    throwOnError: false,
    retry: false,
  })
}
