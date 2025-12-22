"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchFundCertificates } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFundCertificates(fundType?: string) {
  const query = useQuery({
    queryKey: queryKeys.fundCertificates(fundType),
    queryFn: () => fetchFundCertificates(fundType),
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
    refetchIntervalInBackground: true, // Keep refreshing even when tab inactive
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  }
}
