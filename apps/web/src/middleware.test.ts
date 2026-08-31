/**
 * The one path the login redirect must never touch.
 *
 * The middleware answers a request with no session cookie by redirecting to
 * `/login`, which is right for a navigation and wrong for everything Alpha Desk
 * does. A `fetch` cannot follow a redirect to HTML and would report the login
 * page as the answer; an `EventSource` handed HTML reconnects against it every
 * few seconds for as long as the tab is open. So `/api/alpha-desk/*`
 * authenticates inside the handler and answers an API-shaped status instead
 * (ADR-0013), and this pins the exclusion that makes that possible.
 *
 * The matcher is asserted rather than the handler, because the matcher is what
 * decides whether the handler runs at all — and it is one regex away from
 * quietly covering the stream again.
 */

import { NextRequest } from "next/server"
import { describe, expect, it } from "vitest"

import { config, middleware } from "./middleware"

/** The matcher as Next applies it: one pattern, anchored, against a pathname. */
function matches(pathname: string): boolean {
  return config.matcher.some((pattern) => new RegExp(`^${pattern}$`).test(pathname))
}

function signedOut(url: string): NextRequest {
  return new NextRequest(new Request(url))
}

describe("the login redirect", () => {
  it("does not run on the Turn stream", () => {
    expect(matches("/api/alpha-desk/turns/abc/events")).toBe(false)
  })

  it("does not run on any Alpha Desk transport path", () => {
    expect(matches("/api/alpha-desk/threads")).toBe(false)
    expect(matches("/api/alpha-desk/threads/t-1/turns")).toBe(false)
    expect(matches("/api/alpha-desk/turns/abc/cancel")).toBe(false)
    expect(matches("/api/alpha-desk/attachments/a-1")).toBe(false)
  })

  it("still runs on the pages it is for", () => {
    // The exclusion is narrow on purpose: without this, the test above would
    // pass for a matcher that had stopped matching anything at all.
    expect(matches("/")).toBe(true)
    expect(matches("/settings")).toBe(true)
  })

  it("is a redirect to HTML wherever it does run, which is the whole problem", () => {
    const response = middleware(signedOut("http://localhost:3000/"))

    expect(response.status).toBe(307)
    expect(response.headers.get("location")).toContain("/login")
  })
})
