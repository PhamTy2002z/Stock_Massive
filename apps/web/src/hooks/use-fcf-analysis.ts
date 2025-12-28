import { useQuery } from "@tanstack/react-query"
import { fetchFCFAnalysis, type FCFAnalysisResponse } from "@/lib/api"

export function useFCFAnalysis(symbol: string | null) {
  return useQuery<FCFAnalysisResponse>({
    queryKey: ["fcf-analysis", symbol],
    queryFn: () => fetchFCFAnalysis(symbol!),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
