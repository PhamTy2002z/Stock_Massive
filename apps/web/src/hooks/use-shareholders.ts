"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchShareholders } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useShareholders(symbol: string) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.shareholders(symbol),
    queryFn: () => fetchShareholders(symbol),
    staleTime: 10 * 60 * 1000, // 10 minutes
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
