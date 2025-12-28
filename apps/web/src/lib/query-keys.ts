import type { PeriodType, OfficerFilterType, VolumeSpikeParams } from "./api"

export const queryKeys = {
  // Market data
  marketIndices: ["market", "indices"] as const,
  priceBoard: (symbols: string[]) => ["market", "priceBoard", symbols] as const,
  sectorPerformance: ["market", "sectorPerformance"] as const,
  fundCertificates: (fundType?: string) =>
    ["market", "fundCertificates", fundType] as const,
  vn30Overview: ["market", "vn30Overview"] as const,

  // Stock detail
  stock: (symbol: string) => ["stock", symbol] as const,
  stockDetail: (symbol: string) => [...queryKeys.stock(symbol), "detail"] as const,

  // Financials
  incomeStatement: (symbol: string, period: PeriodType, limit: number) =>
    [...queryKeys.stock(symbol), "income", period, limit] as const,
  balanceSheet: (symbol: string, period: PeriodType, limit: number) =>
    [...queryKeys.stock(symbol), "balance", period, limit] as const,
  cashFlow: (symbol: string, period: PeriodType, limit: number) =>
    [...queryKeys.stock(symbol), "cashFlow", period, limit] as const,

  // Ownership
  shareholders: (symbol: string) =>
    [...queryKeys.stock(symbol), "shareholders"] as const,
  officers: (symbol: string, filterBy: OfficerFilterType) =>
    [...queryKeys.stock(symbol), "officers", filterBy] as const,
  insiderDeals: (symbol: string) =>
    [...queryKeys.stock(symbol), "insiderDeals"] as const,

  // Search
  stockSearch: (query: string, limit: number) =>
    ["search", "stocks", query, limit] as const,

  // Analytics
  financialStatements: (limit: number, exchange?: string) =>
    ["analytics", "financialStatements", limit, exchange] as const,
  volumeSpikes: (params: VolumeSpikeParams) =>
    ["analytics", "volumeSpikes", params] as const,

  // Advanced Tab - Order Flow
  orderStats: (symbol: string, days: number) =>
    [...queryKeys.stock(symbol), "orderStats", days] as const,
  priceDepth: (symbol: string) =>
    [...queryKeys.stock(symbol), "priceDepth"] as const,

  // Advanced Tab - Technical
  ratioSummary: (symbol: string) =>
    [...queryKeys.stock(symbol), "ratioSummary"] as const,
  tradingStats: (symbol: string) =>
    [...queryKeys.stock(symbol), "tradingStats"] as const,

  // Advanced Tab - Money Flow
  foreignTrading: (symbol: string, days: number) =>
    [...queryKeys.stock(symbol), "foreignTrading", days] as const,
  propTrading: (symbol: string, days: number) =>
    [...queryKeys.stock(symbol), "propTrading", days] as const,

  // Financial Health
  healthScore: (symbol: string) =>
    [...queryKeys.stock(symbol), "healthScore"] as const,

  // Trend Metrics (Phase 3)
  trendMetrics: (symbol: string, periods: number = 8) =>
    [...queryKeys.stock(symbol), "trendMetrics", periods] as const,

  // Sector Peers (Phase 2 - Sector Comparison Dashboard)
  sectorPeers: (symbol: string) =>
    [...queryKeys.stock(symbol), "sectorPeers"] as const,
} as const
