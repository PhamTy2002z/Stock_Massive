"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME, REFETCH_INTERVAL } from "@/lib/query-config"

export function useMarketIndices() {
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    placeholderData: keepPreviousData,
    staleTime: STALE_TIME.REALTIME,
    refetchInterval: REFETCH_INTERVAL.REALTIME,
    refetchIntervalInBackground: false, // Stop polling when tab inactive
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    dataUpdatedAt: query.dataUpdatedAt,
    refetch: query.refetch,
  }
}
