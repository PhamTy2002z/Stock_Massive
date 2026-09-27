import { describe, expect, it } from "vitest"

import { safeRedirectPath } from "./redirect-path"

describe("safeRedirectPath", () => {
  it("keeps a path on this origin, with its query and fragment", () => {
    expect(safeRedirectPath("/settings")).toBe("/settings")
    expect(safeRedirectPath("/threads/42?tab=sources#top")).toBe("/threads/42?tab=sources#top")
  })

  it("falls back to the root when nothing was asked for", () => {
    expect(safeRedirectPath(undefined)).toBe("/")
    expect(safeRedirectPath(null)).toBe("/")
    expect(safeRedirectPath("")).toBe("/")
  })

  it.each([
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "\\\\evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
    "javascript:alert(1)",
    "settings",
  ])("refuses %j", (next) => {
    expect(safeRedirectPath(next)).toBe("/")
  })

  it("returns the normalised path, not the raw input", () => {
    expect(safeRedirectPath("/a/../settings")).toBe("/settings")
  })
})
