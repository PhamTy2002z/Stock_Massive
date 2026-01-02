"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketIndices() {
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    placeholderData: keepPreviousData,
    staleTime: 15 * 1000, // 15 seconds
    refetchInterval: 15 * 1000,
    refetchIntervalInBackground: false, // Stop polling when tab inactive
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
  }
}
