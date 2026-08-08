"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchPriceDepth, type PriceDepthResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME, REFETCH_INTERVAL } from "@/lib/query-config"

export function usePriceDepth(symbol: string | null) {
  return useQuery<PriceDepthResponse>({
    queryKey: symbol ? queryKeys.priceDepth(symbol) : ["priceDepth", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchPriceDepth(symbol)
    },
    enabled: !!symbol,
    staleTime: STALE_TIME.FAST, // real-time
    refetchInterval: REFETCH_INTERVAL.FAST,
    refetchIntervalInBackground: false, // Stop polling when tab inactive
    // These endpoints answer 501 when the data provider has no such capability
    // (vnstock 4.x dropped several). That is a permanent, per-feature answer —
    // not a page-level failure — so handle it in the component and don't retry.
    throwOnError: false,
    retry: false,
  })
}
