/**
 * The reader's address reaches the API, and nothing that is not an address does.
 *
 * Every auth call leaves from this server, so the API's per-IP limits only see
 * readers apart if the address travels with the call.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

let incoming: Headers | Error = new Headers()

vi.mock("next/headers", () => ({
  headers: async () => {
    if (incoming instanceof Error) throw incoming
    return incoming
  },
}))

const { login } = await import("./api")

const fetchMock = vi.fn<typeof fetch>()

function forwardedFor(): string | null {
  const init = fetchMock.mock.calls[0]?.[1]
  return new Headers(init?.headers).get("x-forwarded-for")
}

describe("auth calls forward the reader's address", () => {
  beforeEach(() => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ access_token: "a", refresh_token: "r", expires_in: 900 }), {
        status: 200,
      }),
    )
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it("sends the first X-Forwarded-For entry", async () => {
    incoming = new Headers({ "x-forwarded-for": "203.0.113.7, 10.0.0.2" })
    await login({ email: "a@example.com", password: "secret-password" })
    expect(forwardedFor()).toBe("203.0.113.7")
  })

  it("falls back to X-Real-IP", async () => {
    incoming = new Headers({ "x-real-ip": "2001:db8::1" })
    await login({ email: "a@example.com", password: "secret-password" })
    expect(forwardedFor()).toBe("2001:db8::1")
  })

  it("drops a value that is not an IP", async () => {
    incoming = new Headers({ "x-forwarded-for": "evil.example" })
    await login({ email: "a@example.com", password: "secret-password" })
    expect(forwardedFor()).toBeNull()
  })

  it("sends none outside a request scope", async () => {
    incoming = new Error("headers() outside a request scope")
    await login({ email: "a@example.com", password: "secret-password" })
    expect(forwardedFor()).toBeNull()
  })
})
