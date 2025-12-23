"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketIndices() {
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 15 * 1000, // 15 seconds
    refetchInterval: 15 * 1000,
    placeholderData: keepPreviousData, // Keep old data while refetching
    refetchIntervalInBackground: false, // Stop polling when tab inactive
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData, // For UI opacity hint
    error: query.error,
    refetch: query.refetch,
  }
}
