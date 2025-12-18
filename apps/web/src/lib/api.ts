const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

export interface PriceBoardItem {
  symbol: string
  ceiling: number | null
  floor: number | null
  ref_price: number | null
  last_price: number | null
  last_vol: number | null
  total_vol: number | null
  total_val: number | null
  change: number | null
  change_pct: number | null
}

export interface MarketIndex {
  symbol: string
  name: string
  value: number
  change: number
  changePercent: number
}

// Index symbol to display name mapping
const INDEX_NAMES: Record<string, string> = {
  VNINDEX: "VN-INDEX",
  VN30: "VN30",
  HNXINDEX: "HNX-INDEX",
  UPCOMINDEX: "UPCOM-INDEX",
}

export const MARKET_INDEX_SYMBOLS = ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchPriceBoard(symbols: string[]): Promise<PriceBoardItem[]> {
  const symbolsParam = symbols.join(",")
  return fetchApi<PriceBoardItem[]>(`/stocks/price-board?symbols=${encodeURIComponent(symbolsParam)}`)
}

export async function fetchMarketIndices(): Promise<MarketIndex[]> {
  const data = await fetchPriceBoard(MARKET_INDEX_SYMBOLS)

  return data.map((item) => ({
    symbol: item.symbol,
    name: INDEX_NAMES[item.symbol] || item.symbol,
    value: item.last_price ?? 0,
    change: item.change ?? 0,
    changePercent: item.change_pct ?? 0,
  }))
}
