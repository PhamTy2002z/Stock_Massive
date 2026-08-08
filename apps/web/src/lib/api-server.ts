import "server-only"
import { getApiBaseUrl, mapMarketIndices } from "./api"
import type { MarketIndex, MarketIndexRaw, SectorPerformanceResponse, StockDetail } from "./api"

async function fetchApiServer<T>(endpoint: string): Promise<T> {
  const url = `${getApiBaseUrl()}${endpoint}`
  const response = await fetch(url, {
    next: { revalidate: 60 }, // ISR: revalidate every 60 seconds
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchMarketIndicesServer(): Promise<MarketIndex[]> {
  const data = await fetchApiServer<MarketIndexRaw[]>("/stocks/market-indices")
  return mapMarketIndices(data)
}

export async function fetchSectorPerformanceServer(): Promise<SectorPerformanceResponse> {
  return fetchApiServer<SectorPerformanceResponse>("/stocks/sector-performance")
}

export async function fetchStockDetailServer(symbol: string): Promise<StockDetail> {
  return fetchApiServer<StockDetail>(`/stocks/${encodeURIComponent(symbol)}/detail`)
}
