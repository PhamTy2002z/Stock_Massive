import { useHealthScore } from "./use-health-score"
import { useTrendMetrics } from "./use-trend-metrics"
import { useSectorPeers } from "./use-sector-peers"
import { useFCFAnalysis } from "./use-fcf-analysis"

/**
 * Combined hook for fetching all financial detail data in parallel.
 * Used by FinancialDetailSheet to load all 4 analysis components.
 * REQUIRES valid symbol - consumer must validate before rendering.
 */
export function useFinancialDetail(symbol: string) {
  const healthScore = useHealthScore(symbol)
  const trendMetrics = useTrendMetrics(symbol)
  const sectorPeers = useSectorPeers(symbol)
  const fcfAnalysis = useFCFAnalysis(symbol)

  const isFetching =
    healthScore.isFetching ||
    trendMetrics.isFetching ||
    sectorPeers.isFetching ||
    fcfAnalysis.isFetching

  return {
    healthScore,
    trendMetrics,
    sectorPeers,
    fcfAnalysis,
    isFetching,
  }
}
