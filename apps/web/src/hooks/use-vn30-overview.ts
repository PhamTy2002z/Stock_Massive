"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchVN30Overview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME, REFETCH_INTERVAL } from "@/lib/query-config"

export function useVN30Overview() {
  const query = useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    placeholderData: keepPreviousData,
    staleTime: STALE_TIME.FAST,
    refetchInterval: REFETCH_INTERVAL.FAST,
    refetchIntervalInBackground: false,
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
