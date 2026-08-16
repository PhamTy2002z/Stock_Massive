/**
 * The registry palette, read out of the one file that declares it (#90).
 *
 * A test over CSS text rather than over a rendered colour, because the two
 * defects ADR-0012 refuses to inherit are both declarations rather than
 * renderings: a series painted pure white, and a token referenced without ever
 * being defined. Neither shows up in jsdom, which resolves no custom property
 * and computes no colour — so the only place they can be caught is here.
 */

import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const css = readFileSync(
  fileURLToPath(new URL("../../../app/globals.css", import.meta.url)),
  "utf8"
)

describe("the registry palette", () => {
  const tokens = [...css.matchAll(/--widget-([a-z-]+):\s*([^;]+);/g)]

  it("is declared in one place, for both themes", () => {
    const names = new Set(tokens.map((match) => match[1]))

    expect(names.size).toBeGreaterThan(8)
    // Every token is declared twice: once light, once dark.
    expect(tokens).toHaveLength(names.size * 2)
  })

  it("paints no mark pure white", () => {
    // The measured defect ADR-0012 refuses to inherit: eight existing charts
    // draw their series in #ffffff, which disappears on a light card. The
    // surface token is exempt because it *is* the card — the rule is about what
    // is drawn on it, not about what it is drawn on.
    const white = tokens
      .filter((match) => match[1] !== "surface")
      .filter((match) => /\b0%\s+100%/.test(match[2]))

    expect(white.map((match) => match[1])).toEqual([])
  })

  it("defines its own up and down rather than referencing undefined ones", () => {
    expect(css).toMatch(/--widget-up:/)
    expect(css).toMatch(/--widget-down:/)
    // `--stock-up` / `--stock-down` are referenced elsewhere in this app and
    // never defined. The registry does not join them.
    expect(css).not.toMatch(/--widget-[a-z-]+:\s*var\(--stock-/)
  })
})
