"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchNewsFeed } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * The news feed, refreshed when the reader comes back rather than on a timer.
 *
 * Headlines arrive in minutes, not in seconds, so a poll would spend the
 * provider's quota to redraw the same list. Returning on focus is the moment
 * something might actually have changed.
 */
export function useNewsFeed() {
  const query = useQuery({
    queryKey: queryKeys.newsFeed,
    queryFn: fetchNewsFeed,
    staleTime: STALE_TIME.STATIC,
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isError: query.isError,
    isFetching: query.isFetching,
    dataUpdatedAt: query.dataUpdatedAt,
    refetch: query.refetch,
  }
}
