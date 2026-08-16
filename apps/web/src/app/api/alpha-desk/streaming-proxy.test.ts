/**
 * What the proxy does with a body it must not read.
 *
 * The existing `proxy.test.ts` covers the two refusals that happen before any
 * upstream call. This file is about the call itself, so `fetch` and the cookie
 * jar are stubbed — but the thing under test is never stubbed: the upstream is
 * a **genuinely slow stream**, emitting over several turns of the event loop,
 * and the assertion is that the first event reaches the caller while the
 * upstream is still writing. A handler that buffered would pass every other
 * check in this file and fail that one.
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

function request(url: string, init: RequestInit = {}): NextRequest {
  return new NextRequest(new Request(url, init))
}

function context(path: string[]) {
  return { params: Promise.resolve({ path }) }
}

/** A gate a test opens by hand, so "slow" is deterministic rather than timed. */
function gate() {
  let open!: () => void
  const opened = new Promise<void>((resolve) => {
    open = resolve
  })
  return { open, opened }
}

/**
 * An upstream that writes one frame, waits to be told, then writes another.
 *
 * Deliberately not a pre-filled stream: a pre-filled one is indistinguishable
 * from a buffered body, which is exactly the failure this file exists to catch.
 */
function slowEventStream(frames: string[], gates: Array<Promise<void>>): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const [index, frame] of frames.entries()) {
        controller.enqueue(encoder.encode(frame))
        const wait = gates[index]
        if (wait) await wait
      }
      controller.close()
    },
  })
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      // Whatever the upstream said about caching or length, the proxy answers
      // with its own headers.
      "Content-Length": "999",
      "Cache-Control": "private",
    },
  })
}

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
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

describe("carrying an event stream", () => {
  it("delivers the first event while the upstream is still writing", async () => {
    const second = gate()
    fetchMock.mockResolvedValue(
      slowEventStream(
        ["id: 1\nevent: turn.snapshot\ndata: {}\n\n", "id: 2\nevent: content.block\ndata: {}\n\n"],
        [second.opened],
      ),
    )

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )

    // The upstream has not been told to write its second frame, and the first
    // is already readable. A buffered handler would still be blocked above.
    const reader = response.body!.getReader()
    const first = new TextDecoder().decode((await reader.read()).value)
    expect(first).toContain("event: turn.snapshot")
    second.open()
    const next = new TextDecoder().decode((await reader.read()).value)
    expect(next).toContain("event: content.block")
    await reader.cancel()
  })

  it("answers with the four streaming headers and no Content-Length", async () => {
    fetchMock.mockResolvedValue(slowEventStream(["id: 1\ndata: {}\n\n"], []))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )

    expect(response.headers.get("Content-Type")).toBe("text/event-stream")
    expect(response.headers.get("Cache-Control")).toBe("no-store, no-transform")
    expect(response.headers.get("X-Accel-Buffering")).toBe("no")
    expect(response.headers.get("Connection")).toBe("keep-alive")
    // The upstream declared 999 bytes; forwarding that would make every hop
    // wait for exactly that many.
    expect(response.headers.get("Content-Length")).toBeNull()
    await response.body?.cancel()
  })

  it("forwards Last-Event-ID so a reconnect says where it got to", async () => {
    fetchMock.mockResolvedValue(slowEventStream(["id: 5\ndata: {}\n\n"], []))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`, {
        headers: { "Last-Event-ID": "4" },
      }),
      context(["turns", "abc", "events"]),
    )

    expect(fetchMock.mock.calls[0][1].headers["Last-Event-ID"]).toBe("4")
    await response.body?.cancel()
  })

  it("obtains a token before the streaming response is returned", async () => {
    const order: string[] = []
    currentAccessToken.mockImplementation(async () => {
      order.push("token")
      return "access-1"
    })
    fetchMock.mockImplementation(async () => {
      order.push("upstream")
      return slowEventStream(["id: 1\ndata: {}\n\n"], [])
    })

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )

    expect(order).toEqual(["token", "upstream"])
    expect(response.status).toBe(200)
    await response.body?.cancel()
  })
})

describe("an expired token", () => {
  it("refreshes once and retries the subscribe exactly once", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(slowEventStream(["id: 1\ndata: {}\n\n"], []))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )

    expect(rotateAccessToken).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer access-1")
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer access-2")
    expect(response.status).toBe(200)
    await response.body?.cancel()
  })

  it("answers an API-shaped 401 rather than redirecting to a login page", async () => {
    // A fetch cannot follow a login redirect, and an EventSource that received
    // HTML would reconnect against it forever.
    fetchMock.mockResolvedValue(json({ detail: "Not authenticated" }, 401))
    rotateAccessToken.mockResolvedValue(null)

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )

    expect(response.status).toBe(401)
    expect(response.headers.get("Content-Type")).toContain("application/json")
    expect(await response.json()).toEqual({ detail: "Not authenticated" })
  })

  it("does not terminate a stream that is already open", async () => {
    // Authentication happens once, before the response goes out. After that the
    // handler is two sockets and nothing else, so an access token expiring
    // mid-Turn cannot end a Turn — the *next* connection authenticates again.
    const second = gate()
    fetchMock.mockResolvedValue(
      slowEventStream(
        ["id: 1\nevent: turn.snapshot\ndata: {}\n\n", "id: 2\nevent: content.block\ndata: {}\n\n"],
        [second.opened],
      ),
    )

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )
    const reader = response.body!.getReader()
    await reader.read()

    // The session is gone as far as anything asking is concerned.
    currentAccessToken.mockResolvedValue(undefined)
    rotateAccessToken.mockResolvedValue(null)
    second.open()

    const next = await reader.read()
    expect(new TextDecoder().decode(next.value)).toContain("event: content.block")
    // Nothing re-asked, because there is nothing left to ask on this path.
    expect(rotateAccessToken).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await reader.cancel()
  })

  it("retries only once, so a route answering 401 twice is reported not looped", async () => {
    // A fresh Response per call: one instance cannot be read twice, and the
    // handler genuinely does make two calls.
    fetchMock.mockImplementation(async () => json({ detail: "Not authenticated" }, 401))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/turns/abc/events`),
      context(["turns", "abc", "events"]),
    )

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(response.status).toBe(401)
  })
})

describe("the buffered path", () => {
  it("still reads a JSON body whole, and says nothing about streaming", async () => {
    fetchMock.mockResolvedValue(json({ cap: 10, count: 0, entries: [] }))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/watchlist/rail`),
      context(["watchlist", "rail"]),
    )

    expect(response.headers.get("Content-Type")).toContain("application/json")
    expect(response.headers.get("Cache-Control")).toBe("no-store")
    expect(response.headers.get("X-Accel-Buffering")).toBeNull()
    expect(await response.json()).toEqual({ cap: 10, count: 0, entries: [] })
  })

  it("carries an admission refusal through as the status and body it was", async () => {
    // 429 and 503 are HTTP outcomes of the POST, never events in a stream.
    fetchMock.mockResolvedValue(
      json(
        { detail: { reason: "user_turn_starts_daily", message: "Đã hết lượt hôm nay." } },
        429,
      ),
    )

    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/threads/t1/turns`, {
        method: "POST",
        headers: { origin: ORIGIN },
        body: JSON.stringify({ turn_id: "id", text: "VCB?" }),
      }),
      context(["threads", "t1", "turns"]),
    )

    expect(response.status).toBe(429)
    expect((await response.json()).detail.reason).toBe("user_turn_starts_daily")
  })
})

describe("the resource allowlist, now that it carries the transport too", () => {
  it("carries threads and turns", async () => {
    fetchMock.mockResolvedValue(json({ threads: [] }))

    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/threads`),
      context(["threads"]),
    )

    expect(response.status).toBe(200)
  })

  it("still refuses everything else before any upstream call", async () => {
    const response = await GET(
      request(`${ORIGIN}/api/alpha-desk/jobs/status`),
      context(["jobs", "status"]),
    )

    expect(response.status).toBe(404)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
