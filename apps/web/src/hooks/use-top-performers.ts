"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchTopPerformers } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useTopPerformers(limit: number = 50, exchange?: string) {
  const query = useQuery({
    queryKey: queryKeys.topPerformers(limit, exchange),
    queryFn: () => fetchTopPerformers(limit, exchange),
    staleTime: 60 * 1000, // 1 min (data doesn't change often)
    refetchInterval: 5 * 60 * 1000, // 5 min auto-refresh
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  }
}
