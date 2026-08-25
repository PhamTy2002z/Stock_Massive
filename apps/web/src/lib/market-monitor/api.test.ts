import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchMarketStockDetail, fetchMarketStocks } from "./api"

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  vi.restoreAllMocks()
})

describe("Market Monitor browser transport", () => {
  it("uses the narrow same-origin auth proxy and binds stock pagination filters", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }))
    globalThis.fetch = fetchMock

    await fetchMarketStocks({
      exchange: "HNX",
      asOf: "2026-08-24",
      preset: "flow",
      sector: "10",
      sort: "foreign_net_20d_vnd",
      direction: "desc",
      cursor: "next-page",
    })

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url).startsWith("/api/alpha-desk/stocks/market-monitor/stocks?")).toBe(true)
    const query = new URL(String(url), "http://localhost").searchParams
    expect(Object.fromEntries(query)).toMatchObject({
      exchange: "HNX",
      as_of: "2026-08-24",
      lens: "flow",
      sector_code: "10",
      sort_by: "foreign_net_20d_vnd",
      direction: "desc",
      cursor: "next-page",
      limit: "25",
      window_days: "253",
    })
    expect(init).toMatchObject({ cache: "no-store" })
  })

  it("encodes a symbol path and preserves an honest upstream failure", async () => {
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ detail: "symbol has no evaluable monitor evidence" }), { status: 404 }))

    await expect(fetchMarketStockDetail("A/B", { exchange: "ALL", asOf: null })).rejects.toMatchObject({
      status: 404,
      message: "symbol has no evaluable monitor evidence",
    })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/stocks/A%2FB?"),
      expect.any(Object),
    )
  })
})
