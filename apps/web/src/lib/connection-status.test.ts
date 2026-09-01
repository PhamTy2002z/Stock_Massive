import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { alphaFetch, AlphaRefusalError } from "./alpha"
import {
  ApiUnavailableError,
  connectionStatus,
  healthUrlFrom,
  UPSTREAM_UNREACHABLE,
} from "./connection-status"

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

    await expect(alphaFetch("/threads")).rejects.toThrow(/không phản hồi|unavailable/i)
    expect(connectionStatus.get()).toBe("waiting")
  })

  it("keeps an answered admission limit as a typed refusal", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(429, { detail: "Too many requests" })))

    await expect(alphaFetch("/threads")).rejects.toBeInstanceOf(AlphaRefusalError)
    expect(connectionStatus.get()).toBe("ready")
  })

  it("keeps a real refusal a refusal", async () => {
    // 404 is the API answering, not failing. Veiling the page over it would
    // hide a genuine "we do not track this symbol" behind a spinner that never
    // resolves.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(404, { detail: "Không có mã này" })))

    await expect(alphaFetch("/threads/missing")).rejects.not.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("ready")
  })

  it("clears waiting when the same operation answers again", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse(503, {
            detail: { reason: UPSTREAM_UNREACHABLE, message: "Restarting" },
          }),
        )
        .mockResolvedValueOnce(jsonResponse(200, [])),
    )

    await expect(alphaFetch("/threads")).rejects.toBeInstanceOf(ApiUnavailableError)
    await alphaFetch("/threads")

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
