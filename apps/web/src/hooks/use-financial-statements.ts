"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchFinancialStatements } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFinancialStatements(limit: number = 50, exchange?: string) {
  const query = useQuery({
    queryKey: queryKeys.financialStatements(limit, exchange),
    queryFn: () => fetchFinancialStatements(limit, exchange),
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
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
