"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  addWatchlistSymbol,
  fetchRail,
  removeWatchlistSymbol,
  retryAnalysis,
  type Rail,
} from "@/lib/alpha"
import { queryKeys } from "@/lib/query-keys"

/**
 * The rail: this user's symbols against the session the data defines.
 *
 * Polled rather than pushed, following the pattern the job progress bar already
 * uses. Nothing on the rail moves during a session — an Analysis is produced
 * from end-of-day data — so the interval exists to pick up the evening's
 * production, not to chase a number.
 *
 * A plain `useQuery` rather than the suspense variant: this component is
 * mounted inside other surfaces later, and a suspense boundary that swallowed
 * the whole page while the rail loaded would be the wrong trade there.
 */
const RAIL_POLL_MS = 60 * 1000

export function useWatchlistRail() {
  return useQuery<Rail>({
    queryKey: queryKeys.watchlistRail,
    queryFn: fetchRail,
    staleTime: 30 * 1000,
    refetchInterval: RAIL_POLL_MS,
    refetchOnWindowFocus: true,
  })
}

/**
 * The three things that change the rail, each refreshing the whole of it.
 *
 * Invalidating the rail rather than patching the cached copy: an addition can
 * seat a symbol *and* queue an Analysis, and a removal frees a slot the cap
 * counts — so the honest answer after any of them is the one the server gives,
 * not one assembled here from a mutation's partial view.
 */
export function useRailMutations() {
  const queryClient = useQueryClient()
  const refreshRail = () => queryClient.invalidateQueries({ queryKey: queryKeys.alpha })

  const add = useMutation({
    mutationFn: (symbol: string) => addWatchlistSymbol(symbol),
    onSuccess: refreshRail,
  })

  const remove = useMutation({
    mutationFn: (symbol: string) => removeWatchlistSymbol(symbol),
    onSuccess: refreshRail,
  })

  const retry = useMutation({
    mutationFn: ({ symbol, tradingDay }: { symbol: string; tradingDay: string }) =>
      retryAnalysis(symbol, tradingDay),
    onSuccess: refreshRail,
  })

  return { add, remove, retry }
}
