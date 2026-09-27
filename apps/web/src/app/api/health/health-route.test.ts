/**
 * The connection probe's server half: it asks the API and repeats only yes or no.
 */

import { afterEach, describe, expect, it, vi } from "vitest"

import { GET } from "./route"

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe("the health route", () => {
  it("asks the API's root health endpoint and answers with the status alone", async () => {
    vi.stubEnv("INTERNAL_API_URL", "http://api:8000/api/v1")
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "healthy", build: "x" }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    const response = await GET()

    expect(fetchMock.mock.calls[0][0]).toBe("http://api:8000/health")
    expect(fetchMock.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal)
    expect(response.status).toBe(200)
    expect(await response.text()).toBe("")
  })

  it("answers 503 when the API refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })))
    const response = await GET()
    expect(response.status).toBe(503)
    expect(await response.text()).toBe("")
  })

  it("answers 503 when the API cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")))
    expect((await GET()).status).toBe(503)
  })
})
