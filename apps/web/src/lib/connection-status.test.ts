import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { searchStocks } from "./api"
import { ApiUnavailableError, connectionStatus, healthUrlFrom } from "./connection-status"

describe("what the app does when the API cannot answer", () => {
  beforeEach(() => {
    connectionStatus.reset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("treats a dropped connection as waiting rather than as a failure", async () => {
    // What the browser throws when there is nothing listening: an API restart,
    // a dropped wifi. It carries no status, so nothing downstream can tell it
    // apart from a bug unless it is classified here.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))
    )

    await expect(searchStocks("VCB")).rejects.toThrow(/không phản hồi|unavailable/i)
    expect(connectionStatus.get()).toBe("waiting")
  })

  it("waits out a rate limit instead of blaming the user for it", async () => {
    // The limit is per-window and the window is seconds long. Telling someone
    // they have been throttled invites them to reload, which spends the very
    // allowance they are waiting on.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(429, { detail: "Too many requests" })))

    await expect(searchStocks("VCB")).rejects.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("waiting")
  })

  it("keeps a real refusal a refusal", async () => {
    // 404 is the API answering, not failing. Veiling the page over it would
    // hide a genuine "we do not track this symbol" behind a spinner that never
    // resolves.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(404, { detail: "Không có mã này" })))

    await expect(searchStocks("VCB")).rejects.not.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("ready")
  })

  it("clears waiting when the same operation answers again", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(503, { detail: "Restarting" }))
        .mockResolvedValueOnce(jsonResponse(200, [])),
    )

    await expect(searchStocks("VCB")).rejects.toBeInstanceOf(ApiUnavailableError)
    await searchStocks("VCB")

    expect(connectionStatus.get()).toBe("ready")
  })
})

describe("where the app looks to see whether the API is back", () => {
  it("asks the health endpoint, which sits outside the versioned prefix", () => {
    expect(healthUrlFrom("http://localhost:8000/api/v1")).toBe("http://localhost:8000/health")
  })

  it("works for a deployment served under a path", () => {
    expect(healthUrlFrom("https://example.com/backend/api/v1")).toBe(
      "https://example.com/backend/health"
    )
  })

  it("falls back to appending when there is no versioned prefix to strip", () => {
    expect(healthUrlFrom("http://localhost:8000")).toBe("http://localhost:8000/health")
  })
})

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}
