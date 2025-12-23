"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchFundCertificates } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFundCertificates(fundType?: string) {
  const query = useQuery({
    queryKey: queryKeys.fundCertificates(fundType),
    queryFn: () => fetchFundCertificates(fundType),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
