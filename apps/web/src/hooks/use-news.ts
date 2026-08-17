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
    // The provider's default sends a refused request to the ErrorBoundary,
    // which for this query would replace the whole shell — the conversation and
    // the board included — because one pane of headlines came back 404 or spent
    // its quota. News is a view, not the app: the feed reports its own failure
    // and offers its own retry, which is also what passing the non-veiling
    // fetch behaviour already promised.
    throwOnError: false,
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
