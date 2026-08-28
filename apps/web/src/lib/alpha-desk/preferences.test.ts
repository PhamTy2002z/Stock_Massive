// @vitest-environment jsdom
/**
 * What this browser remembers, and what it does when the record is not what it
 * expected.
 *
 * Every reader here has to be total. A preference record is written by whichever
 * build the reader last used, so an older shape, a newer shape and outright
 * rubbish are all things a current build will be handed — and none of them may
 * take the workspace down or, worse, resolve to a value the reader never chose.
 */

import { describe, expect, it } from "vitest"

import {
  DEFAULT_PREFERENCES,
  readPreferences,
  writePreferences,
} from "./preferences"

const KEY = "alpha-desk.preferences"

describe("what this browser remembers", () => {
  it("starts with nothing said either way", () => {
    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES)
  })

  it("hands back what was written", () => {
    writePreferences({ signalDeskByDefault: true, chatWidth: 640 })

    const saved = readPreferences()

    expect(saved.signalDeskByDefault).toBe(true)
    expect(saved.chatWidth).toBe(640)
  })

  it("merges rather than replaces, so two callers cannot erase each other", () => {
    // The settings dialog and the shell write different fields and neither
    // knows about the other's.
    writePreferences({ signalDeskByDefault: true })
    writePreferences({ chatWidth: 512 })

    expect(readPreferences()).toEqual({
      signalDeskByDefault: true,
      sidebarOpen: null,
      chatWidth: 512,
    })
  })

  it("separates a collapsed sidebar from one nobody has touched", () => {
    // Null is what lets the shell leave its own opening default alone. A
    // boolean here would mean every existing browser overrode a later change
    // to it.
    expect(readPreferences().sidebarOpen).toBeNull()

    writePreferences({ sidebarOpen: false })
    expect(readPreferences().sidebarOpen).toBe(false)
  })
})

describe("a record this build did not write", () => {
  it("falls back to the defaults when the value is not JSON", () => {
    window.localStorage.setItem(KEY, "not json at all")

    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES)
  })

  it("falls back when the value is JSON but not an object", () => {
    window.localStorage.setItem(KEY, JSON.stringify("dark"))

    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES)
  })

  it("keeps the fields it recognises and defaults the rest", () => {
    // A record written before `chatWidth` existed. The browser has no opinion
    // about the width, which is exactly what null means.
    window.localStorage.setItem(KEY, JSON.stringify({ signalDeskByDefault: true }))

    expect(readPreferences()).toEqual({
      signalDeskByDefault: true,
      sidebarOpen: null,
      chatWidth: null,
    })
  })

  it("refuses a mode that is not a boolean rather than coercing it", () => {
    window.localStorage.setItem(KEY, JSON.stringify({ signalDeskByDefault: "yes" }))

    // "yes" is truthy, and coercing it would switch a mode the reader never
    // chose. Not-a-boolean is not-an-opinion.
    expect(readPreferences().signalDeskByDefault).toBe(false)
  })

  it("refuses a width that could never be one", () => {
    for (const width of [0, -40, Number.NaN, Number.POSITIVE_INFINITY, "wide"]) {
      window.localStorage.setItem(KEY, JSON.stringify({ chatWidth: width }))
      expect(readPreferences().chatWidth).toBeNull()
    }
  })

  it("passes a stored width through unbounded, because only the shell knows the viewport", () => {
    window.localStorage.setItem(KEY, JSON.stringify({ chatWidth: 99_999 }))

    // Clamping belongs to whoever knows how much room there is. Refusing it
    // here would throw away a width that is legitimate on a wider monitor.
    expect(readPreferences().chatWidth).toBe(99_999)
  })
})

describe("a browser that refuses storage", () => {
  it("reads the defaults instead of throwing", () => {
    const original = window.localStorage
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("access denied")
      },
    })

    try {
      expect(readPreferences()).toEqual(DEFAULT_PREFERENCES)
      // And a write is swallowed: the product keeps working at its default,
      // which is the whole reason nothing load-bearing lives here.
      expect(() => writePreferences({ signalDeskByDefault: true })).not.toThrow()
    } finally {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: original,
      })
    }
  })
})
