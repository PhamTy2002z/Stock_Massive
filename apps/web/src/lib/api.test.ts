import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  fetchMarketIndices,
  fetchPriceBoard,
  fetchSectorPerformance,
  fetchVN30Overview,
  getApiBaseUrl,
  mapMarketIndices,
  searchStocks,
  type MarketIndexRaw,
} from "./api"
import { ApiUnavailableError, connectionStatus } from "./connection-status"

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

describe("what a refused request veils", () => {
  const realFetch = globalThis.fetch

  function refuseWith(status: number) {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ detail: "quota" }), {
        status,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch
  }

  beforeEach(() => {
    connectionStatus.reset()
  })

  afterEach(() => {
    globalThis.fetch = realFetch
    connectionStatus.reset()
  })

  it("veils the page when a request a person is waiting on goes unanswered", async () => {
    refuseWith(503)
    await expect(searchStocks("VCB")).rejects.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("waiting")
  })

  it("does not veil the page because a market-data poll was refused", async () => {
    // This is the bug it was written for: the provider behind the price board
    // has a rate limit the chat never touches, and the board re-asks every
    // fifteen seconds. Veiling on that blurred the conversation, blocked the
    // pointer and raised a toast, on a schedule, while nothing the user was
    // doing had failed.
    refuseWith(503)

    await expect(fetchPriceBoard(["VCB"])).rejects.toBeInstanceOf(ApiUnavailableError)
    await expect(fetchMarketIndices()).rejects.toBeInstanceOf(ApiUnavailableError)
    await expect(fetchSectorPerformance()).rejects.toBeInstanceOf(ApiUnavailableError)
    await expect(fetchVN30Overview()).rejects.toBeInstanceOf(ApiUnavailableError)

    expect(connectionStatus.get()).toBe("ready")
  })

  it("does not let a poll lift a veil it did not raise", async () => {
    refuseWith(503)
    await expect(searchStocks("VCB")).rejects.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("waiting")

    globalThis.fetch = (async () =>
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch

    // The board is fine. The thing the person asked for is still not.
    await expect(fetchPriceBoard(["VCB"])).resolves.toEqual([])
    expect(connectionStatus.get()).toBe("waiting")
  })
})
