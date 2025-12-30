import "server-only"
import type { MarketIndex, SectorPerformanceResponse, StockDetail } from "./api"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

async function fetchApiServer<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    next: { revalidate: 60 }, // ISR: revalidate every 60 seconds
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchMarketIndicesServer(): Promise<MarketIndex[]> {
  const data = await fetchApiServer<{ symbol: string; name: string; value: number; change: number; change_pct: number }[]>(
    "/stocks/market-indices"
  )

  return data.map((item) => ({
    symbol: item.symbol,
    name: item.name,
    value: item.value,
    change: item.change,
    changePercent: item.change_pct,
  }))
}

export async function fetchSectorPerformanceServer(): Promise<SectorPerformanceResponse> {
  return fetchApiServer<SectorPerformanceResponse>("/stocks/sector-performance")
}

export async function fetchStockDetailServer(symbol: string): Promise<StockDetail> {
  return fetchApiServer<StockDetail>(`/stocks/${encodeURIComponent(symbol)}/detail`)
}