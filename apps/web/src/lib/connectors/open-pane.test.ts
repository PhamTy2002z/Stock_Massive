import { describe, expect, it } from "vitest"

import { safeAuthorizeUrl } from "./api"
import { readOAuthReturn, stripOAuthReturn } from "./open-pane"

describe("the OAuth return", () => {
  it("is read from the query the API redirects back with", () => {
    expect(readOAuthReturn("?connector=c-1&connector_status=connected")).toEqual({
      outcome: "connected",
      connectorId: "c-1",
    })
    expect(readOAuthReturn("?connector=&connector_status=failed&connector_reason=denied")).toEqual({
      outcome: "failed",
      connectorId: null,
    })
  })

  it("is not read from any other page load", () => {
    expect(readOAuthReturn("")).toBeNull()
    expect(readOAuthReturn("?connector_status=maybe")).toBeNull()
  })

  it("is stripped from the address, keeping everything else", () => {
    expect(
      stripOAuthReturn("http://localhost:3000/?view=chat&connector=c-1&connector_status=failed&connector_reason=x#top"),
    ).toBe("/?view=chat#top")
  })
})

describe("where sign-in may send the browser", () => {
  it("is an http(s) address only", () => {
    expect(safeAuthorizeUrl("https://auth.example.com/authorize?x=1")).toBe(
      "https://auth.example.com/authorize?x=1",
    )
    expect(safeAuthorizeUrl("javascript:alert(1)")).toBeNull()
    expect(safeAuthorizeUrl("not a url")).toBeNull()
    expect(safeAuthorizeUrl(undefined)).toBeNull()
  })
})
