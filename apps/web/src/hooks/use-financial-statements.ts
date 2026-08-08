"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchFinancialStatements } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

export function useFinancialStatements(limit: number = 50, exchange?: string) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.financialStatements(limit, exchange),
    queryFn: () => fetchFinancialStatements(limit, exchange),
    staleTime: STALE_TIME.FREQUENT,
    refetchInterval: 5 * 60 * 1000,
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
