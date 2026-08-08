"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import {
  fetchSectorHistoricalPerformance,
  type SectorHistoricalPeriod,
} from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

export function useSectorHistoricalPerformance(
  period: SectorHistoricalPeriod = "1W"
) {
  const query = useQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    placeholderData: keepPreviousData,
    staleTime: STALE_TIME.STATIC, // historical data
    refetchInterval: 10 * 60 * 1000, // 10 minutes
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
  }
}
