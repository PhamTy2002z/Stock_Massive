"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  fetchAnalysis,
  fetchAnalysisHistory,
  markAnalysisOpened,
  type AnalysisDetail,
  type AnalysisHistory,
} from "@/lib/alpha"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * One symbol's recent Analyses, as far back as the API will browse.
 *
 * Not polled. An Analysis is immutable once published, so the only thing that
 * changes this list is a new session — which the rail's own polling notices,
 * and which invalidates this key along with it.
 */
export function useAnalysisHistory(symbol: string | null) {
  return useQuery<AnalysisHistory>({
    queryKey: queryKeys.analysisHistory(symbol ?? ""),
    queryFn: () => fetchAnalysisHistory(symbol!),
    enabled: !!symbol,
    staleTime: STALE_TIME.STATIC,
  })
}

/**
 * One Analysis in full.
 *
 * Cached indefinitely within the session: a published Analysis is never
 * rewritten, so a second look at last Tuesday's is the same bytes.
 */
export function useAnalysis(symbol: string | null, tradingDay: string | null) {
  return useQuery<AnalysisDetail>({
    queryKey: queryKeys.analysis(symbol ?? "", tradingDay ?? ""),
    queryFn: () => fetchAnalysis(symbol!, tradingDay!),
    enabled: !!symbol && !!tradingDay,
    staleTime: Infinity,
  })
}

/**
 * Report that the user opened one Analysis.
 *
 * The only thing that advances a last-seen date, and it is fired from a user
 * opening an artifact — never from mounting the rail or listing the Watchlist.
 * Clearing ten badges because someone arrived would empty the indicator exactly
 * when it has work to do.
 *
 * The rail is invalidated afterwards so the badge that just cleared is the
 * server's answer rather than a local guess.
 */
export function useMarkAnalysisOpened() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ symbol, tradingDay }: { symbol: string; tradingDay: string }) =>
      markAnalysisOpened(symbol, tradingDay),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlistRail }),
  })
}
