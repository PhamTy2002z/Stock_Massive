import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { getApiBaseUrl, mapMarketIndices, type MarketIndexRaw } from "./api"

describe("getApiBaseUrl (server-side)", () => {
  const original = { ...process.env }

  beforeEach(() => {
    delete process.env.INTERNAL_API_URL
    delete process.env.NEXT_PUBLIC_API_URL
  })

  afterEach(() => {
    process.env = { ...original }
  })

  it("prefers the Docker-internal URL when set", () => {
    process.env.INTERNAL_API_URL = "http://api:8000/api/v1"
    process.env.NEXT_PUBLIC_API_URL = "https://public.example/api/v1"
    expect(getApiBaseUrl()).toBe("http://api:8000/api/v1")
  })

  it("falls back to the public URL", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://public.example/api/v1"
    expect(getApiBaseUrl()).toBe("https://public.example/api/v1")
  })

  it("falls back to localhost when nothing is configured", () => {
    expect(getApiBaseUrl()).toBe("http://localhost:8000/api/v1")
  })
})

describe("mapMarketIndices", () => {
  it("renames change_pct to changePercent and keeps the rest", () => {
    const raw: MarketIndexRaw[] = [
      { symbol: "VNINDEX", name: "VN-Index", value: 1300.5, change: -4.2, change_pct: -0.32 },
    ]

    expect(mapMarketIndices(raw)).toEqual([
      { symbol: "VNINDEX", name: "VN-Index", value: 1300.5, change: -4.2, changePercent: -0.32 },
    ])
  })

  it("maps an empty list to an empty list", () => {
    expect(mapMarketIndices([])).toEqual([])
  })
})
