/**
 * Which address the proxy compares an `Origin` against.
 *
 * `nextUrl.origin` is built from the address this process is **bound** to
 * rather than from the request: a Next server listening on `0.0.0.0:3000`
 * behind a reverse proxy reports `http://localhost:3000` for a browser that
 * asked for `https://app.example.com`. An origin check against it therefore
 * refuses every Alpha Desk write the day a proxy is put in front — which is the
 * deployment this product asks for, and a failure invisible to a unit test on
 * either side of the proxy. It was found by the end-to-end acceptance (#92) and
 * is pinned here so it stays found.
 *
 * The session and the network are both stubbed, so a request that survives the
 * origin gate reaches a fetch that answers with a status nothing else produces.
 * That is the whole assertion: **403, or the marker**.
 */

import { NextRequest } from "next/server"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/auth/bearer", () => ({
  currentAccessToken: async () => undefined,
  rotateAccessToken: async () => null,
}))

const { POST } = await import("./[...path]/route")

// The bound address, which is what `nextUrl.origin` reads — deliberately not
// the address any of these requests claims to have been sent to.
const BOUND = "http://localhost:3000"

function request(init: RequestInit): NextRequest {
  return new NextRequest(new Request(`${BOUND}/api/alpha-desk/threads`, init))
}

const context = { params: Promise.resolve({ path: ["threads"] }) }

/** A status no refusal in this handler produces, so it can only mean "forwarded". */
const FORWARDED = 599

beforeEach(() => {
  vi.stubGlobal("fetch", async () => new Response("{}", { status: FORWARDED }))
})

afterEach(() => {
  delete process.env.APP_ORIGIN
  vi.unstubAllGlobals()
})

describe("the origin check behind a reverse proxy", () => {
  it("accepts a write whose origin matches the forwarded host", async () => {
    const response = await POST(
      request({
        method: "POST",
        headers: {
          origin: "https://app.example.com",
          "x-forwarded-host": "app.example.com",
          "x-forwarded-proto": "https",
        },
        body: "{}",
      }),
      context,
    )

    expect(response.status).toBe(FORWARDED)
  })

  it("accepts a write whose origin matches the Host header", async () => {
    const response = await POST(
      request({
        method: "POST",
        headers: { origin: "http://127.0.0.1:3010", host: "127.0.0.1:3010" },
        body: "{}",
      }),
      context,
    )

    expect(response.status).toBe(FORWARDED)
  })

  it("refuses a foreign origin arriving at this app's host", async () => {
    // The shape of a real cross-site write: the browser sends this app's host,
    // because that is where the request went, and the attacker's origin.
    const response = await POST(
      request({
        method: "POST",
        headers: {
          origin: "https://evil.example",
          "x-forwarded-host": "app.example.com",
          "x-forwarded-proto": "https",
        },
        body: "{}",
      }),
      context,
    )

    expect(response.status).toBe(403)
  })

  it("honours a configured origin over whatever the headers claim", async () => {
    process.env.APP_ORIGIN = "https://app.example.com"

    const refused = await POST(
      request({
        method: "POST",
        headers: { origin: "https://other.example", host: "other.example" },
        body: "{}",
      }),
      context,
    )
    expect(refused.status).toBe(403)

    const allowed = await POST(
      request({
        method: "POST",
        headers: { origin: "https://app.example.com", host: "app.example.com" },
        body: "{}",
      }),
      context,
    )
    expect(allowed.status).toBe(FORWARDED)
  })

  it("falls back to the bound address when nothing names a host", async () => {
    // Not a browser: every one of them sends `Host`. The fallback keeps the
    // check meaningful for anything speaking to this process directly.
    const response = await POST(
      request({ method: "POST", headers: { origin: BOUND }, body: "{}" }),
      context,
    )

    expect(response.status).toBe(FORWARDED)
  })
})
