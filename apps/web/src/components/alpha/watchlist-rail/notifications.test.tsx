// @vitest-environment jsdom
/**
 * How a user learns an Analysis is ready, with no external channel in v1.
 *
 * Three claims, and each is one an obvious implementation gets wrong:
 *
 * *The badge clears one symbol at a time.* It is driven by a per-user
 * per-symbol last-seen date that advances only when that Analysis is opened.
 * Clearing on app open would empty the indicator exactly when it has work to do.
 *
 * *The status line is one line, and it is conditional three ways.* A weekday,
 * past 16:15 ICT, and no Snapshot for today. Weekends show nothing: there was
 * no session to collect, so nothing is late.
 *
 * *The history boundary is visible.* Ninety sessions is a browsing depth, and a
 * reader who cannot see the edge reads an empty scroll as the end of history.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { RailEntry } from "@/lib/alpha"
import { RailEntryRow } from "./rail-entry"
import { RailHeader } from "./rail-header"
import { SystemStatusLine } from "./status-line"
import { historyBoundaryNotice, missingSessionNotice } from "./state-copy"

afterEach(cleanup)

const SESSION = "2026-08-12"

function entry(overrides: Partial<RailEntry> = {}): RailEntry {
  return {
    symbol: "FPT",
    state: "ready",
    added_at: "2026-08-01T02:00:00Z",
    latest: {
      symbol: "FPT",
      trading_day: SESSION,
      verdict: "accumulate",
      schema_version: 1,
      created_at: "2026-08-12T13:00:00Z",
    },
    failure: null,
    unread: false,
    last_seen_analysis_date: SESSION,
    ...overrides,
  }
}

/** An instant, given as the Vietnam wall clock the rule is written against. */
function ict(day: string, hour: number, minute: number): Date {
  const stamp = `${day}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00+07:00`
  return new Date(stamp)
}

// 2026-08-12 is a Wednesday; 2026-08-15 a Saturday, 2026-08-16 a Sunday.
const WEDNESDAY = "2026-08-12"
const SATURDAY = "2026-08-15"
const SUNDAY = "2026-08-16"

describe("the unread badge", () => {
  it("counts the symbols with an Analysis the user has not opened", () => {
    render(<RailHeader tradingDay={SESSION} count={4} cap={10} unreadCount={3} />)

    expect(screen.getByLabelText("3 unread Analyses")).toHaveTextContent("3")
  })

  it("shows nothing at zero rather than a grey nought", () => {
    render(<RailHeader tradingDay={SESSION} count={4} cap={10} unreadCount={0} />)

    expect(screen.queryByLabelText(/unread Analyses/)).not.toBeInTheDocument()
  })

  it("marks the individual symbol, so the badge can clear one at a time", () => {
    render(
      <RailEntryRow
        entry={entry({ unread: true, last_seen_analysis_date: null })}
        tradingDay={SESSION}
        onRemove={vi.fn()}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByLabelText("FPT has an unread Analysis")).toBeInTheDocument()
  })

  it("leaves no mark on a symbol whose latest Analysis was already opened", () => {
    render(
      <RailEntryRow
        entry={entry({ unread: false })}
        tradingDay={SESSION}
        onRemove={vi.fn()}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.queryByLabelText(/unread Analysis/)).not.toBeInTheDocument()
  })

  it("opens a symbol only when the user asks, never on render", () => {
    const onToggle = vi.fn()
    render(
      <RailEntryRow
        entry={entry({ unread: true })}
        tradingDay={SESSION}
        onRemove={vi.fn()}
        onRetry={vi.fn()}
        onToggle={onToggle}
      />,
    )

    expect(onToggle).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "FPT" }))

    expect(onToggle).toHaveBeenCalledWith("FPT")
  })
})

describe("the one system status line", () => {
  it("says the session has not arrived on a weekday after the deadline", () => {
    // Wednesday 17:00 ICT, and the newest session the store holds is Tuesday's.
    expect(missingSessionNotice("2026-08-11", ict(WEDNESDAY, 17, 0))).toBe(
      "Dữ liệu phiên 12/08 chưa về.",
    )
  })

  it("stays silent before the collection deadline", () => {
    // Nothing is late at 16:00: the run has not happened yet, and saying so
    // would be noise every single afternoon.
    expect(missingSessionNotice("2026-08-11", ict(WEDNESDAY, 16, 0))).toBeNull()
  })

  it("stays silent once the session has arrived", () => {
    expect(missingSessionNotice(WEDNESDAY, ict(WEDNESDAY, 17, 0))).toBeNull()
  })

  it("never appears at a weekend", () => {
    // There was no session to collect, so nothing is missing.
    expect(missingSessionNotice("2026-08-14", ict(SATURDAY, 18, 0))).toBeNull()
    expect(missingSessionNotice("2026-08-14", ict(SUNDAY, 18, 0))).toBeNull()
  })

  it("reads the deadline on the market's clock, not the viewer's", () => {
    // 10:30 UTC is 17:30 in Vietnam — past the deadline, on the same weekday.
    // A viewer in London must see the same line as one in Ho Chi Minh City.
    expect(missingSessionNotice("2026-08-11", new Date("2026-08-12T10:30:00Z"))).toBe(
      "Dữ liệu phiên 12/08 chưa về.",
    )
  })

  it("renders once for the whole rail, not once per symbol", () => {
    render(<SystemStatusLine tradingDay="2026-08-11" now={ict(WEDNESDAY, 17, 0)} />)

    expect(screen.getAllByRole("status")).toHaveLength(1)
  })

  it("renders nothing at all when the condition does not hold", () => {
    const { container } = render(
      <SystemStatusLine tradingDay={WEDNESDAY} now={ict(WEDNESDAY, 17, 0)} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})

describe("browsing history", () => {
  it("names the boundary when there is more behind it", () => {
    expect(historyBoundaryNotice(90, true)).toMatch(/90 phiên gần nhất/)
  })

  it("says nothing when the window holds everything there is", () => {
    // A boundary announced on a symbol with eleven Analyses teaches the reader
    // that the rail always stops somewhere, which is the opposite of the point.
    expect(historyBoundaryNotice(90, false)).toBeNull()
  })

  it("keeps the depth the API reported rather than hard-coding ninety", () => {
    expect(historyBoundaryNotice(30, true)).toMatch(/30 phiên gần nhất/)
  })
})
