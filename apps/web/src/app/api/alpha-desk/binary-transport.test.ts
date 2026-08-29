/**
 * What the proxy does with a body that is not JSON.
 *
 * `streaming-proxy.test.ts` covers the two bodies that already worked: JSON
 * and an event stream. This file is the third and fourth shape the docstring
 * on `route.ts` now describes — a multipart upload going up, and a binary
 * download coming down — plus the regression the change must not cause: the
 * JSON path reading exactly the bytes it always read.
 *
 * Every assertion here compares bytes, not "looks right" — a UTF-8 decode of
 * a binary body corrupts silently, with no status code and no thrown error,
 * so a test that only checked `response.status` would pass against the bug
 * this phase exists to fix.
 */

import { createHash } from "node:crypto"

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

function request(url: string, init: RequestInit = {}): NextRequest {
  return new NextRequest(new Request(url, init))
}

function context(path: string[]) {
  return { params: Promise.resolve({ path }) }
}

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex")
}

/** `Uint8Array#buffer` is typed `ArrayBufferLike`; the Fetch types below want `ArrayBuffer`. */
function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
}

function concat(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const out = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) {
    out.set(chunk, offset)
    offset += chunk.length
  }
  return out
}

/**
 * A multipart body carrying bytes no UTF-8 decoder can round-trip.
 *
 * `0xff 0xfe` is not valid UTF-8 anywhere in that position; a decode-and-
 * re-encode (`await request.text()`) replaces it with U+FFFD, so this
 * fixture fails loudly — a hash mismatch — the moment the buffering
 * regresses to `text()`.
 */
const BOUNDARY = "----visgnite-test-boundary"
function multipartBody(): Uint8Array {
  const encoder = new TextEncoder()
  const binaryPart = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0xff, 0xfe, 0x00, 0x01, 0x02])
  return concat([
    encoder.encode(
      `--${BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="x.png"\r\nContent-Type: image/png\r\n\r\n`,
    ),
    binaryPart,
    encoder.encode(`\r\n--${BOUNDARY}--\r\n`),
  ])
}

function binaryResponse(bytes: Uint8Array, extraHeaders: Record<string, string> = {}): Response {
  return new Response(toArrayBuffer(bytes), {
    status: 200,
    headers: { "Content-Type": "application/octet-stream", ...extraHeaders },
  })
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  currentAccessToken.mockResolvedValue("access-1")
  rotateAccessToken.mockResolvedValue("access-2")
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe("a multipart upload going up", () => {
  it("reaches the upstream fetch call byte-for-byte, boundary and all", async () => {
    const bytes = multipartBody()
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }))

    await POST(
      request(`${ORIGIN}/api/alpha-desk/attachments`, {
        method: "POST",
        headers: {
          origin: ORIGIN,
          "Content-Type": `multipart/form-data; boundary=${BOUNDARY}`,
        },
        body: toArrayBuffer(bytes),
      }),
      context(["attachments"]),
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers["Content-Type"]).toBe(`multipart/form-data; boundary=${BOUNDARY}`)
    // Not a string: the boundary and the PNG bytes inside it must never pass
    // through a UTF-8 decode.
    expect(init.body).toBeInstanceOf(ArrayBuffer)
    expect(sha256(new Uint8Array(init.body))).toBe(sha256(bytes))
  })

  it("replays the same bytes on the 401 retry, because the buffer is not a stream", async () => {
    const bytes = multipartBody()
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }))

    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/attachments`, {
        method: "POST",
        headers: {
          origin: ORIGIN,
          "Content-Type": `multipart/form-data; boundary=${BOUNDARY}`,
        },
        body: toArrayBuffer(bytes),
      }),
      context(["attachments"]),
    )

    expect(response.status).toBe(200)
    expect(rotateAccessToken).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const firstBody = new Uint8Array(fetchMock.mock.calls[0][1].body)
    const secondBody = new Uint8Array(fetchMock.mock.calls[1][1].body)
    expect(sha256(firstBody)).toBe(sha256(bytes))
    expect(sha256(secondBody)).toBe(sha256(bytes))
  })
})

describe("a binary download coming down", () => {
  it("reaches the browser byte-for-byte", async () => {
    const bytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0xff, 0xfe, 0x00, 0x10, 0x20, 0x30])
    fetchMock.mockResolvedValue(binaryResponse(bytes, { "Content-Type": "image/png" }))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/attachments/abc`),
      context(["attachments", "abc"]),
    )

    const received = new Uint8Array(await response.arrayBuffer())
    expect(sha256(received)).toBe(sha256(bytes))
    expect(response.headers.get("Content-Type")).toBe("image/png")
  })

  it("carries Content-Disposition and X-Content-Type-Options through", async () => {
    const bytes = new Uint8Array([1, 2, 3])
    fetchMock.mockResolvedValue(
      binaryResponse(bytes, {
        "Content-Type": "image/png",
        "Content-Disposition": 'attachment; filename="chart.png"',
        "X-Content-Type-Options": "nosniff",
      }),
    )

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/attachments/abc`),
      context(["attachments", "abc"]),
    )

    expect(response.headers.get("Content-Disposition")).toBe('attachment; filename="chart.png"')
    expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff")
  })

  it("omits Content-Disposition and X-Content-Type-Options when upstream sent neither", async () => {
    // assets (favicons) never set these; passthrough must not invent them.
    fetchMock.mockResolvedValue(binaryResponse(new Uint8Array([1]), { "Content-Type": "image/x-icon" }))

    const response = await GET(request(`${ORIGIN}/api/alpha-desk/assets/1`), context(["assets", "1"]))

    expect(response.headers.has("Content-Disposition")).toBe(false)
    expect(response.headers.has("X-Content-Type-Options")).toBe(false)
  })
})

describe("the JSON path, unchanged", () => {
  it("still sends the request body as text, not as a buffer", async () => {
    const payload = JSON.stringify({ symbol: "FPT" })
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ cap: 10 }), { status: 200 }))

    await POST(
      request(`${ORIGIN}/api/alpha-desk/watchlist`, {
        method: "POST",
        headers: { origin: ORIGIN, "Content-Type": "application/json" },
        body: payload,
      }),
      context(["watchlist"]),
    )

    const [, init] = fetchMock.mock.calls[0]
    expect(typeof init.body).toBe("string")
    expect(init.body).toBe(payload)
    expect(init.headers["Content-Type"]).toBe("application/json")
  })

  it("still buffers the JSON response through the same text-decoding path as before", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ cap: 10, count: 1, entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )

    const response = await GET(request(`${ORIGIN}/api/alpha-desk/watchlist/rail`), context(["watchlist", "rail"]))

    expect(response.headers.get("Cache-Control")).toBe("no-store")
    expect(await response.json()).toEqual({ cap: 10, count: 1, entries: [] })
  })
})

describe("the allowlist, now that attachments is on it", () => {
  it("carries attachments", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }))

    const response = await GET(request(`${ORIGIN}/api/alpha-desk/attachments/abc`), context(["attachments", "abc"]))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(response.status).toBe(200)
  })

  it("still refuses a resource nobody put on the allowlist", async () => {
    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/downloads/report.pdf`),
      context(["downloads", "report.pdf"]),
    )

    expect(response.status).toBe(404)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
