"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import {
  fetchSectorHistoricalPerformance,
  type SectorHistoricalPeriod,
} from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useSectorHistoricalPerformance(
  period: SectorHistoricalPeriod = "1W"
) {
  const query = useQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000, // 5 minutes (historical data)
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
