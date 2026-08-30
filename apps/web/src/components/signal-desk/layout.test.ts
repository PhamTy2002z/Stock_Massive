/**
 * The one rule this end owns, held equal to the table the server packs with.
 *
 * The spans arrive decided. A collapse invented here that the server did not
 * anticipate would be the browser re-laying out a board and calling it a
 * breakpoint, so the table below is the whole of what this file may do — and it
 * mirrors `studies/layout.py`, whose own test asserts every row adds to twelve.
 */

import { describe, expect, it } from "vitest"

import { COLUMNS, gridColumn, NARROW, spanAt } from "./layout"

describe("a panel wide enough for the server's arrangement", () => {
  it.each([
    [12, 12],
    [6, 6],
    [4, 4],
    [3, 3],
  ])("keeps a span of %i as %i", (span, expected) => {
    expect(spanAt(span, NARROW)).toBe(expected)
  })
})

describe("a panel too narrow for thirds", () => {
  it.each([
    [3, 6],
    [4, 6],
    [6, 12],
    [12, 12],
  ])("widens a span of %i to %i", (span, expected) => {
    expect(spanAt(span, NARROW - 1)).toBe(expected)
  })

  it("collapses in two steps rather than one", () => {
    // A third going straight to the full width turns a row of three charts into
    // three screens of scrolling; a pair still reads.
    expect(spanAt(4, 320)).toBe(6)
    expect(spanAt(4, 320)).not.toBe(COLUMNS)
  })
})

describe("spans that should never have arrived", () => {
  it("clamps a span wider than the grid", () => {
    expect(spanAt(40, NARROW)).toBe(COLUMNS)
  })

  it("keeps a span of zero on the grid rather than making it disappear", () => {
    expect(spanAt(0, NARROW)).toBe(1)
  })
})

describe("the declaration a block carries", () => {
  it("says the same number twice, so nothing downstream does the maths again", () => {
    expect(gridColumn(6, NARROW)).toBe("span 6 / span 6")
    expect(gridColumn(4, 320)).toBe("span 6 / span 6")
  })
})
