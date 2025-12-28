import { useHealthScore } from "./use-health-score"
import { useTrendMetrics } from "./use-trend-metrics"
import { useSectorPeers } from "./use-sector-peers"
import { useFCFAnalysis } from "./use-fcf-analysis"

/**
 * Combined hook for fetching all financial detail data in parallel.
 * Used by FinancialDetailSheet to load all 4 analysis components.
 */
export function useFinancialDetail(symbol: string | null) {
  const healthScore = useHealthScore(symbol)
  const trendMetrics = useTrendMetrics(symbol)
  const sectorPeers = useSectorPeers(symbol)
  const fcfAnalysis = useFCFAnalysis(symbol)

  const isLoading =
    healthScore.isLoading ||
    trendMetrics.isLoading ||
    sectorPeers.isLoading ||
    fcfAnalysis.isLoading

  const hasError =
    healthScore.error ||
    trendMetrics.error ||
    sectorPeers.error ||
    fcfAnalysis.error

  return {
    healthScore,
    trendMetrics,
    sectorPeers,
    fcfAnalysis,
    isLoading,
    hasError,
  }
}
