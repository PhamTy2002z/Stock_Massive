"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchPropTrading, type PropTradingItem } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function usePropTrading(symbol: string | null, days: number = 30) {
  return useQuery<PropTradingItem[]>({
    queryKey: symbol ? queryKeys.propTrading(symbol, days) : ["propTrading", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchPropTrading(symbol, days)
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
