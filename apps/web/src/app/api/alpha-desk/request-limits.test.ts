/**
 * What the proxy refuses or rewrites about the request itself: paths that step
 * out of the allowlist, bodies too large to buffer, the reader's address, and a
 * reader who hangs up.
 */

import { NextRequest } from "next/server"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const currentAccessToken = vi.fn<() => Promise<string | undefined>>()
const rotateAccessToken = vi.fn<() => Promise<string | null>>()

vi.mock("@/lib/auth/bearer", () => ({
  currentAccessToken: () => currentAccessToken(),
  rotateAccessToken: () => rotateAccessToken(),
}))

const { GET, POST } = await import("./[...path]/route")

const ORIGIN = "http://localhost:3000"
const MB = 1024 * 1024

function request(url: string, init: RequestInit & { duplex?: "half" } = {}): NextRequest {
  return new NextRequest(new Request(url, init))
}

function context(path: string[]) {
  return { params: Promise.resolve({ path }) }
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  currentAccessToken.mockResolvedValue("access-1")
  rotateAccessToken.mockResolvedValue("access-2")
  fetchMock = vi.fn().mockResolvedValue(
    new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
  )
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe("path segments", () => {
  it.each([
    [["threads", "..", "..", "admin"]],
    [["threads", "."]],
    [["threads", "", "turns"]],
    [["threads", "a/b"]],
    [["threads", "a\\b"]],
    [["threads", "%2e%2e"]],
    [["threads", "%2F"]],
  ])("refuses %j before anything goes upstream", async (path) => {
    const response = await GET(request(`${ORIGIN}/api/alpha-desk/threads/x`), context(path))
    expect(response.status).toBe(404)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("still carries an ordinary path", async () => {
    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/threads/t-1`),
      context(["threads", "t-1"]),
    )
    expect(response.status).toBe(200)
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/threads\/t-1$/)
  })
})

describe("the body cap", () => {
  it("refuses a declared length over the cap without reading it", async () => {
    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/attachments`, {
        method: "POST",
        headers: {
          origin: ORIGIN,
          "Content-Type": "application/octet-stream",
          "Content-Length": String(7 * MB),
        },
        body: new Uint8Array(16),
      }),
      context(["attachments"]),
    )
    expect(response.status).toBe(413)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("stops reading a body with no declared length once it passes the cap", async () => {
    let pulled = 0
    const chunk = new Uint8Array(MB)
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        pulled += 1
        // Endless, as a hostile chunked upload would be.
        controller.enqueue(chunk)
      },
    })
    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/attachments`, {
        method: "POST",
        headers: { origin: ORIGIN, "Content-Type": "application/octet-stream" },
        body,
        duplex: "half",
      }),
      context(["attachments"]),
    )
    expect(response.status).toBe(413)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(pulled).toBeLessThan(10)
  })

  it("carries a body under the cap byte for byte", async () => {
    const bytes = new Uint8Array(5 * MB).map((_, index) => index % 251)
    await POST(
      request(`${ORIGIN}/api/alpha-desk/attachments`, {
        method: "POST",
        headers: { origin: ORIGIN, "Content-Type": "application/octet-stream" },
        body: bytes,
      }),
      context(["attachments"]),
    )
    const [, init] = fetchMock.mock.calls[0]
    expect(init.body).toBeInstanceOf(ArrayBuffer)
    expect(Buffer.compare(Buffer.from(init.body), Buffer.from(bytes))).toBe(0)
  })
})

describe("the reader's address", () => {
  async function forwardedFor(headers: Record<string, string>): Promise<string | undefined> {
    await GET(request(`${ORIGIN}/api/alpha-desk/threads`, { headers }), context(["threads"]))
    return fetchMock.mock.calls[0][1].headers["X-Forwarded-For"]
  }

  it("passes on the first address of the chain, and only that", async () => {
    expect(await forwardedFor({ "x-forwarded-for": "203.0.113.7, 10.0.0.2" })).toBe("203.0.113.7")
  })

  it("accepts an IPv6 address", async () => {
    expect(await forwardedFor({ "x-forwarded-for": "2001:db8::1" })).toBe("2001:db8::1")
  })

  it("falls back to X-Real-IP when the chain's first entry is not an address", async () => {
    expect(
      await forwardedFor({ "x-forwarded-for": "evil, 203.0.113.7", "x-real-ip": "198.51.100.4" }),
    ).toBe("198.51.100.4")
  })

  it("sends nothing when no header names an address", async () => {
    expect(await forwardedFor({ "x-forwarded-for": "not-an-ip" })).toBeUndefined()
  })
})

describe("a reader who hangs up", () => {
  it("hands the request's own signal to the upstream fetch", async () => {
    const incoming = request(`${ORIGIN}/api/alpha-desk/turns/t-1/events`)
    await GET(incoming, context(["turns", "t-1", "events"]))
    expect(fetchMock.mock.calls[0][1].signal).toBe(incoming.signal)
  })
})
