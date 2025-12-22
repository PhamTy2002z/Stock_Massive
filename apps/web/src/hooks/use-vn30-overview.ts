"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchVN30Overview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVN30Overview() {
  const query = useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
    refetchIntervalInBackground: true, // Keep data fresh even when tab inactive
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  }
}
