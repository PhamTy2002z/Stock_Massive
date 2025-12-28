"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchMarketOverview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketOverview() {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.marketOverview,
    queryFn: fetchMarketOverview,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data,
    isFetching,
    refetch,
  }
}
