// @vitest-environment jsdom
/**
 * Whether one greeting stays put.
 *
 * The point of the module is that the line does *not* change on every visit, so
 * the tests are about the window holding and about the two ways storage lets a
 * reader down: a value some other build wrote, and a browser that refuses
 * storage outright.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { greetingFor } from "./greeting"
import { GREETING_ROLL_TTL_MS, stickyRoll } from "./greeting-roll"

describe("stickyRoll", () => {
  const KEY = "visgnite.greeting-roll"

  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("hands back the same roll for two hours, then draws again", () => {
    const drawn = stickyRoll(1_000)

    expect(stickyRoll(1_000 + GREETING_ROLL_TTL_MS - 1)).toBe(drawn)

    vi.spyOn(Math, "random").mockReturnValue(drawn === 0.5 ? 0.25 : 0.5)
    const next = stickyRoll(1_000 + GREETING_ROLL_TTL_MS)
    expect(next).not.toBe(drawn)
    expect(stickyRoll(1_000 + GREETING_ROLL_TTL_MS)).toBe(next)
  })

  it("holds one line across the window", () => {
    stickyRoll(0)
    const held = greetingFor("Evening", "Tỷ", stickyRoll(0))

    for (const at of [1, 60_000, GREETING_ROLL_TTL_MS - 1]) {
      expect(greetingFor("Evening", "Tỷ", stickyRoll(at))).toBe(held)
    }
  })

  it("draws fresh when the stored value is not a usable roll", () => {
    for (const raw of ['{"roll":1,"until":9e99}', '{"roll":-0.1,"until":9e99}', '{"roll":0.5}', "not json", "[]"]) {
      window.localStorage.setItem(KEY, raw)
      vi.spyOn(Math, "random").mockReturnValue(0.125)
      expect(stickyRoll(0)).toBe(0.125)
      vi.restoreAllMocks()
    }
  })

  it("still returns a roll when storage is unavailable", () => {
    vi.spyOn(window.localStorage, "getItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("blocked")
    })

    const roll = stickyRoll(0)
    expect(roll).toBeGreaterThanOrEqual(0)
    expect(roll).toBeLessThan(1)
  })
})
