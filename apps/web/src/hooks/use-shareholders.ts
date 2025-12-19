"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchShareholders } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useShareholders(symbol: string | null) {
  return useQuery({
    queryKey: symbol ? queryKeys.shareholders(symbol) : ["shareholders", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchShareholders(symbol)
    },
    enabled: !!symbol,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}
