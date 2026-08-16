/**
 * What this surface is allowed to say.
 *
 * Two claims, and both of them are about omission — the kind a plausible
 * implementation breaks by being helpful. The activity line is generic because
 * the catalog is not published; a Turn that stopped early gets a sentence
 * because a stable code on screen is an internal name leaking into an answer.
 */

import { describe, expect, it } from "vitest"

import {
  ACTIVITY_COPY,
  FIRST_RUN,
  KNOWN_TERMINAL_REASONS,
  terminalSentence,
} from "./copy"
import type { ActivityPhase } from "./types"

// The v1 catalog, as `apps/api/src/agent/tools/` registers it. Listed here
// rather than imported because the point of the assertion is that these names
// have no route to the browser at all.
const TOOL_NAMES = [
  "get_analysis",
  "get_company_profile",
  "get_financials",
  "get_price_series",
  "get_watchlist",
  "screen_universe",
  "search_news",
]

const PHASES: ActivityPhase[] = ["searching", "reading_data", "analyzing", "preparing_visual"]

describe("the activity line", () => {
  it("has a phrase and an expanded summary for every phase the stream can send", () => {
    for (const phase of PHASES) {
      expect(ACTIVITY_COPY[phase].line.length).toBeGreaterThan(0)
      expect(ACTIVITY_COPY[phase].summary.length).toBeGreaterThan(0)
    }
  })

  it("names no tool, in the line or behind the disclosure", () => {
    // Expanding the line must not become how a user learns the catalog. The
    // summary describes the kind of work; the Tool Call Trace holds the detail.
    const everything = PHASES.map(
      (phase) => `${ACTIVITY_COPY[phase].line} ${ACTIVITY_COPY[phase].summary}`,
    ).join(" ")

    for (const name of TOOL_NAMES) {
      expect(everything).not.toContain(name)
    }
  })

  it("stays generic — no symbol, no argument, no result", () => {
    // A phase describes work, so it carries no ticker-shaped token and no
    // figure. Either would mean the line was assembled from a call rather than
    // from the phase the publisher named.
    for (const phase of PHASES) {
      const text = `${ACTIVITY_COPY[phase].line} ${ACTIVITY_COPY[phase].summary}`
      expect(text).not.toMatch(/\b[A-Z]{3}\b/)
      expect(text).not.toMatch(/\d/)
    }
  })
})

describe("a Turn that stopped early", () => {
  it("gives every reason the lifecycle can write a sentence of its own", () => {
    for (const reason of KNOWN_TERMINAL_REASONS) {
      expect(terminalSentence(reason)).not.toBe(terminalSentence("something_unmapped"))
    }
  })

  it("never shows the code, not even one it has not learned", () => {
    expect(terminalSentence("a_reason_this_surface_has_not_learned")).not.toContain("_")
    expect(terminalSentence(null)).not.toContain("_")
  })

  it("says something rather than nothing when the reason is absent", () => {
    expect(terminalSentence(null).length).toBeGreaterThan(0)
  })
})

describe("the first run", () => {
  it("states that any Universe symbol may be discussed and what the Watchlist is for", () => {
    expect(FIRST_RUN.universeRule).toMatch(/Universe/)
    expect(FIRST_RUN.universeRule).toMatch(/Watchlist/)
  })

  it("states the scope boundary in user language", () => {
    expect(FIRST_RUN.scopeBoundary).toMatch(/bốn trục/)
    expect(FIRST_RUN.scopeBoundary).toMatch(/không tính toán tuỳ ý/)
  })

  it("publishes no catalog", () => {
    const everything = Object.values(FIRST_RUN).join(" ")

    for (const name of TOOL_NAMES) {
      expect(everything).not.toContain(name)
    }
  })
})
