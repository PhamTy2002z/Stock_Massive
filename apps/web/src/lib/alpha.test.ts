/** @vitest-environment jsdom */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { alphaFetch, AlphaRefusalError } from "./alpha"
import { ApiUnavailableError, connectionStatus, UPSTREAM_UNREACHABLE } from "./connection-status"

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

describe("alphaFetch outage handling", () => {
  beforeEach(() => {
    connectionStatus.reset()
  })

  afterEach(() => {
    connectionStatus.reset()
    vi.unstubAllGlobals()
  })

  it("reads the proxy's unreachable upstream as silence, not as a refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: { reason: UPSTREAM_UNREACHABLE, message: "Đang thử lại…" } }, 503),
        ),
    )

    await expect(alphaFetch("/threads")).rejects.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("waiting")
  })

  it("reports silence when the request never completed at all", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")))

    await expect(alphaFetch("/threads")).rejects.toBeInstanceOf(ApiUnavailableError)
    expect(connectionStatus.get()).toBe("waiting")
  })

  it("leaves an admission refusal its status and its reason", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: { reason: "daily_cap_reached", message: "Hết lượt hôm nay." } }, 503),
        ),
    )

    const error = await alphaFetch("/turns").catch((thrown: unknown) => thrown)

    expect(error).toBeInstanceOf(AlphaRefusalError)
    expect((error as AlphaRefusalError).reason).toBe("daily_cap_reached")
    expect((error as AlphaRefusalError).status).toBe(503)
    // The API answered: this operation is not what the page is waiting on.
    expect(connectionStatus.get()).toBe("ready")
  })
})

describe("sendAlpha body headers", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("does not set Content-Type on a FormData body, leaving the boundary to the browser", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    const form = new FormData()
    form.append("file", new Blob(["x"]), "x.png")
    await alphaFetch("/attachments", { method: "POST", body: form })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers).not.toHaveProperty("Content-Type")
    expect(init.body).toBe(form)
  })

  it("still sets Content-Type: application/json for a plain object body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await alphaFetch("/threads", { method: "POST", body: JSON.stringify({ title: "FPT" }) })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" })
  })
})
