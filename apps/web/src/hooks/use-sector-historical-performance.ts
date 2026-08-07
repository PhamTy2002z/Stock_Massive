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
    // One dashboard block among many. The API answers 503 with a reason while
    // its nightly job has not produced this period yet; bubbling that to the
    // page-level error boundary replaced the whole homepage section with a red
    // error card. Handle it inline instead.
    throwOnError: false,
    retry: false,
  })

  return {
    data: query.data,
    error: query.error,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
  }
}
