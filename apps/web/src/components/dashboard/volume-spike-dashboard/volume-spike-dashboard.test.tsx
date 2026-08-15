// @vitest-environment jsdom
/**
 * What the screen says when the data is thin.
 *
 * These three pieces carry the honesty of the whole screen: the band that is
 * always there, the state that refuses to look like an empty result, and the
 * switch whose labels must never promise the whole market.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { VolumeSpikeResponse } from "@/lib/api"
import { signalIssueSentence } from "@/lib/signal-issues"
import { CoverageBand } from "./coverage-band"
import { InsufficientDataNotice } from "./insufficient-notice"
import { ScopeTabs } from "./scope-tabs"

afterEach(cleanup)

function signal(overrides: Partial<VolumeSpikeResponse> = {}): VolumeSpikeResponse {
  return {
    scope: "profit_leaders",
    trading_day: "2026-08-12",
    threshold: 1.5,
    coverage: { state: "ready", evaluated: 50, total: 50 },
    freshness: "fresh",
    cohort_version: { id: 12, reporting_period: "2026-06-30" },
    issues: [],
    spikes: [],
    unevaluable: [],
    ...overrides,
  }
}

describe("CoverageBand", () => {
  it("states the session and the coverage even when everything is healthy", () => {
    render(<CoverageBand signal={signal()} />)

    expect(screen.getByText("2026-08-12")).toBeInTheDocument()
    expect(screen.getByText(/toàn bộ 50 mã/i)).toBeInTheDocument()
    expect(screen.getByText(/phiên mới nhất/i)).toBeInTheDocument()
  })

  it("says how many of the scope it could evaluate when the answer is partial", () => {
    render(
      <CoverageBand
        signal={signal({
          coverage: { state: "partial", evaluated: 47, total: 50 },
          freshness: "lagging",
          issues: ["lagging_market_data"],
        })}
      />,
    )

    expect(screen.getByText(/47\/50 mã/)).toBeInTheDocument()
    expect(screen.getByText(/chưa phải phiên mới nhất/i)).toBeInTheDocument()
  })

  it("renders issue codes as sentences, never as codes", () => {
    render(<CoverageBand signal={signal({ issues: ["stale_market_data"] })} />)

    expect(screen.queryByText(/stale_market_data/)).not.toBeInTheDocument()
    expect(screen.getByText(/cũ hơn 7 ngày/i)).toBeInTheDocument()
  })
})

describe("SignalIssue", () => {
  it("explains a volume basis break in Vietnamese", () => {
    expect(signalIssueSentence("volume_basis_break")).toMatch(
      /thay đổi số cổ phiếu.*không cùng cơ sở/i,
    )
  })
})

describe("InsufficientDataNotice", () => {
  it("explains the state instead of showing an empty result", () => {
    render(<InsufficientDataNotice />)

    expect(screen.getByText(/chưa đủ dữ liệu để kết luận/i)).toBeInTheDocument()
    expect(screen.getByText(/21 phiên liên tiếp/i)).toBeInTheDocument()
  })
})

describe("ScopeTabs", () => {
  it("labels the second scope as the Universe, not the market", () => {
    render(<ScopeTabs scope="profit_leaders" onScopeChange={() => {}} />)

    expect(screen.getByText("Toàn bộ Universe")).toBeInTheDocument()
    expect(screen.queryByText(/toàn thị trường/i)).not.toBeInTheDocument()
    // The Universe's size is a bound on collection, not something the reader
    // has to reason about (docs/adr/0001).
    expect(screen.queryByText(/100/)).not.toBeInTheDocument()
  })

  it("reports the scope the reader switched to", () => {
    const onScopeChange = vi.fn()
    render(<ScopeTabs scope="profit_leaders" onScopeChange={onScopeChange} />)

    // Radix activates a tab on mouse down rather than on click, which is what
    // makes a tab feel immediate under a real pointer.
    fireEvent.mouseDown(screen.getByText("Toàn bộ Universe"), { button: 0 })

    expect(onScopeChange).toHaveBeenCalledWith("universe")
  })
})
