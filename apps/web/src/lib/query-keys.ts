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
  topPerformers: (limit: number, exchange?: string) =>
    ["analytics", "topPerformers", limit, exchange] as const,
  volumeSpikes: (params: VolumeSpikeParams) =>
    ["analytics", "volumeSpikes", params] as const,
} as const
