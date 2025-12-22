"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketIndices() {
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
    refetchIntervalInBackground: true, // Keep refreshing even when tab inactive
    refetchOnWindowFocus: true, // Refresh when user returns to browser tab
    refetchOnMount: true, // Always fetch on component mount
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  }
}
