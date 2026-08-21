import { describe, expect, it } from "vitest"

import { GREETINGS, greetingFor, plainGreeting } from "./greeting"
import type { PartOfDay } from "./market-session"

const PARTS: PartOfDay[] = ["Morning", "Afternoon", "Evening"]

describe("plainGreeting", () => {
  it("is the neutral line the product has always opened on", () => {
    expect(plainGreeting("Morning", "Phạm Phước Tỷ")).toBe("Morning, Phạm Phước Tỷ")
    expect(plainGreeting("Afternoon", "Phạm Phước Tỷ")).toBe("Afternoon, Phạm Phước Tỷ")
    expect(plainGreeting("Evening", "Phạm Phước Tỷ")).toBe("Evening, Phạm Phước Tỷ")
  })

  it("still reads as a greeting for an account with no name", () => {
    expect(plainGreeting("Evening", null)).toBe("Evening")
  })
})

describe("greetingFor", () => {
  it("walks the whole list as the roll crosses it", () => {
    const lines = PARTS.flatMap((part) =>
      GREETINGS[part].map((_, index) =>
        greetingFor(part, "Tỷ", index / GREETINGS[part].length),
      ),
    )

    expect(lines).toEqual([
      "Morning, Tỷ",
      "Rise and shine, Tỷ",
      "Coffee first, Tỷ?",
      "Look who's up, Tỷ",
      "Fresh start, Tỷ",
      "Hello, early bird",
      "Afternoon, Tỷ",
      "Back at it, Tỷ",
      "Survived lunch, Tỷ",
      "Still going strong, Tỷ",
      "Hello again, Tỷ",
      "Afternoon, deskmate",
      "Evening, Tỷ",
      "Burning the candle, Tỷ?",
      "Late shift, Tỷ",
      "Winding down, Tỷ",
      "Off the clock, Tỷ",
      "Hello, night owl",
    ])
  })

  it("stays inside the list at the very top of the range", () => {
    // `Math.random()` never returns 1, but a caller reading the signature
    // could hand one over, and an off-list index would render `undefined`.
    for (const part of PARTS) {
      expect(greetingFor(part, "Tỷ", 1)).toBe(
        GREETINGS[part][GREETINGS[part].length - 1]("Tỷ"),
      )
      expect(greetingFor(part, "Tỷ", 0.9999999)).toBeTruthy()
    }
  })

  it("leaves no line dangling on a comma when there is no name", () => {
    for (const part of PARTS) {
      for (const line of GREETINGS[part]) {
        const rendered = line(null)
        expect(rendered).not.toMatch(/,\s*$/)
        expect(rendered).not.toMatch(/,\s*[?!]/)
        expect(rendered.trim()).toBe(rendered)
      }
    }
  })
})
