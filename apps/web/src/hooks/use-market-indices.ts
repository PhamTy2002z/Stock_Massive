"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketIndices() {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 15 * 1000, // 15 seconds
    refetchInterval: 15 * 1000,
    refetchIntervalInBackground: false, // Stop polling when tab inactive
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  // data is ALWAYS defined with useSuspenseQuery - no null check needed
  return {
    data,
    isFetching,
    refetch,
  }
}
