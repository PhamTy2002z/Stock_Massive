"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchVN30Overview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVN30Overview() {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
