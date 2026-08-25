/**
 * What the Alpha Desk proxy refuses before it forwards anything.
 *
 * The handler carries the user's session cookie to an API that trusts a bearer
 * token, so the two checks in front of it are the only things standing between
 * a signed-in browser and a request it did not make. Both refuse *before* any
 * upstream call, which is what lets these run without a network at all — a test
 * that had to mock `fetch` would be testing the mock.
 */

import { NextRequest } from "next/server"
import { describe, expect, it } from "vitest"

import { DELETE, POST } from "./[...path]/route"

const ORIGIN = "http://localhost:3000"

function request(url: string, init: RequestInit = {}): NextRequest {
  return new NextRequest(new Request(url, init))
}

function context(path: string[]) {
  return { params: Promise.resolve({ path }) }
}

describe("the resource allowlist", () => {
  it("admits only the market-monitor subtree under stocks", async () => {
    const monitor = await POST(
      request(`${ORIGIN}/api/alpha-desk/stocks/market-monitor/overview`, {
        method: "POST",
        headers: { origin: "https://evil.example" },
      }),
      context(["stocks", "market-monitor", "overview"]),
    )
    const unrelatedStock = await POST(
      request(`${ORIGIN}/api/alpha-desk/stocks/jobs`, {
        method: "POST",
        headers: { origin: ORIGIN },
      }),
      context(["stocks", "jobs"]),
    )

    expect(monitor.status).toBe(403)
    expect(unrelatedStock.status).toBe(404)
  })

  it("carries the flag action, which is a write on a message the user owns", async () => {
    // Not a 404: `messages` is on the allowlist for the flag of ADR-0016.
    // Upstream still resolves the Thread's owner, so widening the proxy here
    // widens nothing anybody can reach.
    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/messages/7/flag`, {
        method: "POST",
        headers: { origin: "https://evil.example" },
        body: JSON.stringify({ reason: "wrong_figure" }),
      }),
      context(["messages", "7", "flag"]),
    )

    // Refused for the origin rather than for the resource, which is what shows
    // the path itself got through the allowlist.
    expect(response.status).toBe(403)
  })

  it("refuses a path it was never meant to carry", async () => {
    // Without this, a signed-in user's token reaches every route they could
    // type — the operational ones behind the admin check included.
    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/jobs/trigger`, {
        method: "POST",
        headers: { origin: ORIGIN },
      }),
      context(["jobs", "trigger"]),
    )

    expect(response.status).toBe(404)
  })
})

describe("cross-origin writes", () => {
  it("refuses a state-changing request from another origin", async () => {
    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/watchlist`, {
        method: "POST",
        headers: { origin: "https://evil.example" },
        body: JSON.stringify({ symbol: "FPT" }),
      }),
      context(["watchlist"]),
    )

    expect(response.status).toBe(403)
  })

  it("refuses a state-changing request that names no origin at all", async () => {
    // SameSite=Lax already stops most of this, but Lax is a browser default
    // rather than a promise this handler makes.
    const response = await DELETE(
      request(`${ORIGIN}/api/alpha-desk/watchlist/FPT`, { method: "DELETE" }),
      context(["watchlist", "FPT"]),
    )

    expect(response.status).toBe(403)
  })

  it("checks the allowlist before the origin, so an unknown path never 403s", async () => {
    // The two refusals must not be able to disagree about what happened: an
    // unknown resource is unknown whoever asked for it.
    const response = await POST(
      request(`${ORIGIN}/api/alpha-desk/jobs/trigger`, {
        method: "POST",
        headers: { origin: "https://evil.example" },
      }),
      context(["jobs", "trigger"]),
    )

    expect(response.status).toBe(404)
  })
})
