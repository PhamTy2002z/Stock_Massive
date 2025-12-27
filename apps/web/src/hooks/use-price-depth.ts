"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchPriceDepth, type PriceDepthResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function usePriceDepth(symbol: string | null) {
  return useQuery<PriceDepthResponse>({
    queryKey: symbol ? queryKeys.priceDepth(symbol) : ["priceDepth", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchPriceDepth(symbol)
    },
    enabled: !!symbol,
    staleTime: 30 * 1000, // 30 seconds - real-time
    refetchInterval: 30 * 1000, // Auto-refresh every 30s
    refetchIntervalInBackground: false, // Stop polling when tab inactive
    retry: 2,
  })
}
