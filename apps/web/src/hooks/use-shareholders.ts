"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchShareholders } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useShareholders(symbol: string | null) {
  const query = useQuery({
    queryKey: symbol ? queryKeys.shareholders(symbol) : ["shareholders", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchShareholders(symbol)
    },
    enabled: !!symbol,
    staleTime: 10 * 60 * 1000, // 10 minutes
    placeholderData: keepPreviousData,
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
