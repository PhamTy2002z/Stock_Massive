/**
 * The palette, and the one rule it enforces rather than trusts.
 *
 * A frame says what its numbers *are* and this file decides what that looks
 * like. Two properties matter enough to pin down:
 *
 * **Every meaning the engine may declare has a colour here.** A word the server
 * accepts and the browser has no token for is a claim a Study made that nobody
 * ever sees, and it fails silently — the chart simply draws in the default.
 *
 * **The focus is spent once.** It is the only role that says something about the
 * picture rather than about a number, and two of them say nothing at all.
 */

import { describe, expect, it } from "vitest"

import { colorFor, resolveRoles, SERIES } from "./chart-theme"

/** The server's own vocabulary, from `studies/contracts.py`. */
const PLAIN = ["series", "muted", "focus", "up", "down", "neutral"]
const CATEGORIES = [1, 2, 3, 4, 5, 6].map((slot) => `category:${slot}`)

describe("the colour for one declared meaning", () => {
  it("draws every word the engine is allowed to say", () => {
    for (const role of [...PLAIN, ...CATEGORIES]) {
      expect(colorFor(role)).toMatch(/^hsl\(var\(--widget-[a-z0-9-]+\)\)$/)
    }
  })

  it("gives each meaning its own token, so two claims never look alike", () => {
    const painted = [...PLAIN, ...CATEGORIES].map(colorFor)

    expect(new Set(painted).size).toBe(painted.length)
  })

  it("falls back to the default series colour for a word it has no colour for", () => {
    // A seventh group, a role from a later build, a typo on the server: all of
    // them draw as an ordinary series rather than as nothing.
    expect(colorFor("category:7")).toBe(SERIES)
    expect(colorFor("bullish")).toBe(SERIES)
    expect(colorFor(null)).toBe(SERIES)
    expect(colorFor(undefined)).toBe(SERIES)
    expect(colorFor(3)).toBe(SERIES)
  })
})

describe("spending the focus", () => {
  it("keeps a single focus exactly where the frame put it", () => {
    const { roles, focusSpent } = resolveRoles([null, "focus", "up"])

    expect(roles).toEqual([null, "focus", "up"])
    expect(focusSpent).toBe(false)
  })

  it("drops every focus when a frame marked more than one", () => {
    // Nothing highlighted rather than everything: the numbers are still right
    // and only the emphasis was wrong. Withdrawn to "said nothing", so each
    // widget falls back to whatever it draws an unclaimed element in.
    const { roles, focusSpent } = resolveRoles(["focus", "down", "focus"])

    expect(roles).toEqual([null, "down", null])
    expect(focusSpent).toBe(true)
    expect(colorFor(roles[0])).toBe(SERIES)
  })

  it("leaves every other role alone when it drops the focus", () => {
    const { roles } = resolveRoles(["focus", "focus", "category:3", null])

    expect(roles[2]).toBe("category:3")
    expect(roles[3]).toBeNull()
  })

  it("reads a missing entry as a claim nobody made", () => {
    const { roles, focusSpent } = resolveRoles([undefined, null])

    expect(roles).toEqual([null, null])
    expect(focusSpent).toBe(false)
  })
})
