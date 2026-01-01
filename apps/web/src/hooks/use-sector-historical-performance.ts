"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import {
  fetchSectorHistoricalPerformance,
  type SectorHistoricalPeriod,
} from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useSectorHistoricalPerformance(
  period: SectorHistoricalPeriod = "1W"
) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    staleTime: 5 * 60 * 1000, // 5 minutes (historical data)
    refetchInterval: 10 * 60 * 1000, // 10 minutes
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return { data, isFetching, refetch }
}
