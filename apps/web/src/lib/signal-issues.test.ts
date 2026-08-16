/**
 * The Vietnamese half of the Signal Issue vocabulary, checked against the
 * vocabulary itself.
 *
 * `src/stocks/signals/issues.py` is the closed set, and it is closed precisely
 * so that this app can hold one sentence per code. A code added there and not
 * here is a blank on the screen — or worse, the code itself rendered verbatim,
 * which is the one thing the Analysis artifact must never do
 * (`docs/specs/0002` §5). Reading the enum rather than restating it is what
 * makes that impossible to forget: the file the codes live in is the file this
 * test asserts against.
 */

import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import { SIGNAL_ISSUE_SENTENCES, signalIssueSentence } from "./signal-issues"

const ISSUES_PY = join(
  process.cwd(),
  "..",
  "api",
  "src",
  "stocks",
  "signals",
  "issues.py",
)

/** Every `NAME = "value"` member of the enum, as the backend spells them. */
function backendCodes(): string[] {
  const source = readFileSync(ISSUES_PY, "utf8")
  return [...source.matchAll(/^\s{4}[A-Z_]+ = "([a-z_]+)"$/gm)].map(
    (match) => match[1],
  )
}

describe("the Signal Issue vocabulary", () => {
  it("reads the backend enum rather than a copy of it", () => {
    const codes = backendCodes()
    expect(codes).toContain("insufficient_history")
    expect(codes.length).toBeGreaterThan(20)
  })

  it("holds one Vietnamese sentence per code the backend can emit", () => {
    const missing = backendCodes().filter(
      (code) => !(code in SIGNAL_ISSUE_SENTENCES),
    )

    expect(missing).toEqual([])
  })

  it("names no code this app cannot receive", () => {
    const codes = new Set(backendCodes())
    const unknown = Object.keys(SIGNAL_ISSUE_SENTENCES).filter(
      (code) => !codes.has(code),
    )

    expect(unknown).toEqual([])
  })

  it("never renders the code itself, not even for one it has not learned", () => {
    const sentence = signalIssueSentence("a_code_from_the_future")

    expect(sentence).not.toContain("a_code_from_the_future")
    expect(sentence.length).toBeGreaterThan(0)
  })

  it("says what is missing rather than what to do about it", () => {
    // A reason that advised a reader would be the recommendation the citation
    // contract exists to keep out of a figure (`src/alpha/reasons.py`).
    const advice = /nên mua|nên bán|nên nắm giữ|khuyến nghị/i

    for (const sentence of Object.values(SIGNAL_ISSUE_SENTENCES)) {
      expect(sentence).not.toMatch(advice)
    }
  })
})
