"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchFundCertificates } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

export function useFundCertificates(fundType?: string) {
  const query = useQuery({
    queryKey: queryKeys.fundCertificates(fundType),
    queryFn: () => fetchFundCertificates(fundType),
    staleTime: STALE_TIME.FREQUENT,
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
