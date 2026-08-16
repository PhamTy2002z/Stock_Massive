// @vitest-environment jsdom
/**
 * What opening an Analysis does besides drawing it.
 *
 * The badge is the whole point: `last_seen_analysis_date` advances for **that
 * symbol and that session**, because it moves when a specific Analysis is
 * opened rather than when the app is (`docs/specs/0002` §3). Clearing ten
 * badges because someone arrived empties the indicator exactly when it has work
 * to do, and that failure is invisible in a screenshot — so it is checked here.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { AnalysisDetail } from "@/lib/alpha"
import { AnalysisCard } from "./analysis-card"

const reportOpened = vi.fn()
const analysis: { data: AnalysisDetail | undefined; isPending: boolean } = {
  data: undefined,
  isPending: true,
}

vi.mock("@/hooks/use-analysis", () => ({
  useAnalysis: () => analysis,
  useMarkAnalysisOpened: () => ({ mutate: reportOpened }),
}))

beforeEach(() => {
  reportOpened.mockClear()
  analysis.data = undefined
  analysis.isPending = true
})

afterEach(cleanup)

describe("opening an Analysis", () => {
  it("advances the last-seen date for that symbol and that session only", () => {
    render(<AnalysisCard symbol="FPT" tradingDay="2026-08-12" />)

    expect(reportOpened).toHaveBeenCalledTimes(1)
    expect(reportOpened).toHaveBeenCalledWith({
      symbol: "FPT",
      tradingDay: "2026-08-12",
    })
  })

  it("says it is loading rather than rendering an empty artifact", () => {
    render(<AnalysisCard symbol="FPT" tradingDay="2026-08-12" />)

    expect(screen.getByText(/Đang tải Analysis/)).toBeInTheDocument()
  })

  it("says so when the Analysis could not be read", () => {
    analysis.isPending = false
    render(<AnalysisCard symbol="FPT" tradingDay="2026-08-12" />)

    expect(screen.getByText(/Không đọc được Analysis/)).toBeInTheDocument()
  })

  it("renders the artifact once the payload is in hand", () => {
    analysis.isPending = false
    analysis.data = {
      symbol: "FPT",
      trading_day: "2026-08-12",
      verdict: "accumulate",
      schema_version: 1,
      created_at: "2026-08-12T18:00:00+00:00",
      payload: {
        evidence: {
          symbol: "FPT",
          tradingDay: "2026-08-12",
          sections: [{ axis: "technical", health: "ok", figures: [] }],
        },
        citedFieldIds: [],
      },
    }

    render(<AnalysisCard symbol="FPT" tradingDay="2026-08-12" />)

    expect(screen.getByText("accumulate")).toBeInTheDocument()
    expect(screen.getAllByRole("tab")).toHaveLength(4)
  })
})
