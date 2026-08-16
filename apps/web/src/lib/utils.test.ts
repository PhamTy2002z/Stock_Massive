import { describe, expect, it } from "vitest"

import { cn } from "./utils"

/**
 * The one thing `cn` has to get right that is not obvious.
 *
 * `text-*` is two utilities wearing one prefix, and `tailwind-merge` tells them
 * apart from a model of Tailwind's default scale. Every step of this product's
 * ramp is a custom name, so without the extension in `utils.ts` each one is
 * read as a colour and dropped the moment a real colour follows it — silently,
 * with the class still in the source.
 *
 * The failure has no symptom a reviewer would catch: the label simply inherits
 * the body's 15px, which looks like a design decision rather than a bug. So it
 * is checked here rather than trusted.
 */
describe("cn", () => {
  const RAMP = ["eyebrow", "micro", "meta", "control", "row"] as const

  it.each(RAMP)("keeps text-%s beside a text colour", (step) => {
    expect(cn(`text-${step}`, "text-ink-6")).toBe(`text-${step} text-ink-6`)
  })

  it("still lets one ramp step override another", () => {
    // They are sizes, so the later one has to win — that is the whole point of
    // running the classes through a merge rather than concatenating them.
    expect(cn("text-row", "text-control")).toBe("text-control")
  })

  it("still lets one colour override another", () => {
    expect(cn("text-ink-4", "text-ink-1")).toBe("text-ink-1")
  })

  it("leaves Tailwind's own scale working", () => {
    expect(cn("text-sm", "text-lg")).toBe("text-lg")
  })
})
