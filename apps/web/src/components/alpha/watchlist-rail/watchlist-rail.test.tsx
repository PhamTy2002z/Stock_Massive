// @vitest-environment jsdom
/**
 * What the rail says, and what it must never say.
 *
 * Three claims carry this screen, and each is one a plausible implementation
 * gets wrong:
 *
 * *The session is dated and never called "today".* The latest session with a
 * Snapshot is frequently not today — Saturday shows Friday — so "today" would
 * be a lie in the one place a user checks first.
 *
 * *`failed` never renders empty.* It shows the most recent Analysis that does
 * exist, plus a dated label for the session that is missing. An empty cell says
 * there is nothing to see while a month of history sits behind it.
 *
 * *The cap is a permanent count, and `unsupported` is not in it.* A symbol the
 * Universe dropped stays on the rail with its remove action and costs the user
 * no slot, because they did not cause it.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { RailEntry } from "@/lib/alpha"
import { AddSymbolForm } from "./add-symbol-form"
import { RailEntryRow } from "./rail-entry"
import { RailHeader } from "./rail-header"
import { onDemandSentence, sessionLabel, stateSentence } from "./state-copy"

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

function row(overrides: Partial<RailEntry> = {}, tradingDay: string | null = SESSION) {
  return render(
    <RailEntryRow
      entry={entry(overrides)}
      tradingDay={tradingDay}
      onRemove={vi.fn()}
      onRetry={vi.fn()}
    />,
  )
}

describe("the session the rail is showing", () => {
  it("names the Trading Day by date and never says today", () => {
    render(<RailHeader tradingDay={SESSION} count={3} cap={10} />)

    expect(screen.getByText(/phiên 12\/08/)).toBeInTheDocument()
    expect(screen.queryByText(/hôm nay/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\btoday\b/i)).not.toBeInTheDocument()
  })

  it("reads the API's plain date without putting it through a time zone", () => {
    // A Trading Day has no instant behind it. Parsed into a `Date` it acquires
    // one, and every zone west of UTC+7 then renders the day before — naming
    // the wrong session for every reader outside Asia.
    expect(sessionLabel("2026-08-12")).toBe("phiên 12/08")
  })

  it("says so plainly when nothing has closed yet rather than inventing a day", () => {
    render(<RailHeader tradingDay={null} count={0} cap={10} />)

    expect(screen.getByText(/chưa có phiên nào chốt dữ liệu/i)).toBeInTheDocument()
  })
})

describe("the cap", () => {
  it("shows as a count from the first symbol rather than at the eleventh add", () => {
    render(<RailHeader tradingDay={SESSION} count={1} cap={10} />)

    expect(screen.getByText("1/10")).toBeInTheDocument()
  })

  it("renders an overflow rather than hiding it", () => {
    // A symbol restored to the Universe revives whether or not there is room.
    // The overflow stands and adding is what gets blocked.
    render(<RailHeader tradingDay={SESSION} count={11} cap={10} />)

    expect(screen.getByText("11/10")).toBeInTheDocument()
  })
})

describe("the five states", () => {
  it("gives every state a Vietnamese sentence, including the healthy ones", () => {
    const states = ["ready", "pending", "producing", "failed", "unsupported"] as const

    for (const state of states) {
      expect(stateSentence(state, SESSION).length).toBeGreaterThan(0)
    }
  })

  it("labels a ready symbol with the session its Analysis is for", () => {
    row({ state: "ready" })

    expect(screen.getByText("Ready")).toBeInTheDocument()
    expect(screen.getByText(/Đã có Analysis cho phiên 12\/08/)).toBeInTheDocument()
  })

  it("distinguishes a symbol not yet reached from one that failed", () => {
    row({ state: "pending", latest: null })

    expect(screen.getByText(/Chưa tới lượt dựng Analysis/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Retry/)).not.toBeInTheDocument()
  })

  it("shows a run mid-flight as producing", () => {
    row({ state: "producing" })

    expect(screen.getByText("Producing")).toBeInTheDocument()
    expect(screen.getByText(/Đang dựng Analysis cho phiên 12\/08/)).toBeInTheDocument()
  })

  it("keeps an unsupported symbol on the rail with its own remove action", () => {
    row({ state: "unsupported" })

    expect(screen.getByText("Unsupported")).toBeInTheDocument()
    expect(screen.getByText(/không còn trong Universe/)).toBeInTheDocument()
    expect(screen.getByLabelText("Remove FPT")).toBeInTheDocument()
  })
})

describe("a failed session", () => {
  const failed = {
    state: "failed" as const,
    latest: {
      symbol: "FPT",
      trading_day: "2026-08-11",
      verdict: "hold",
      schema_version: 1,
      created_at: "2026-08-11T13:00:00Z",
    },
    failure: {
      code: "missing_market_snapshot",
      message: "no session data for FPT",
      attempts: 1,
      max_attempts: 3,
      exhausted: false,
    },
  }

  it("shows the most recent Analysis that does exist rather than an empty cell", () => {
    row(failed)

    expect(screen.getByText("hold")).toBeInTheDocument()
    expect(screen.getByText(/phiên 11\/08/)).toBeInTheDocument()
  })

  it("names the session that is missing, by date", () => {
    row(failed)

    expect(screen.getByText(/Chưa có Analysis cho phiên 12\/08/)).toBeInTheDocument()
  })

  it("explains the failure as a sentence and never as its code", () => {
    row(failed)

    expect(screen.queryByText(/missing_market_snapshot/)).not.toBeInTheDocument()
    expect(screen.getByText(/chưa có dữ liệu thị trường/i)).toBeInTheDocument()
  })

  it("offers a retry for the session it is missing", () => {
    const onRetry = vi.fn()
    render(
      <RailEntryRow
        entry={entry(failed)}
        tradingDay={SESSION}
        onRemove={vi.fn()}
        onRetry={onRetry}
      />,
    )

    fireEvent.click(screen.getByLabelText("Retry FPT"))

    expect(onRetry).toHaveBeenCalledWith("FPT", SESSION)
  })

  it("drops the retry at the ceiling instead of offering one more press", () => {
    row({
      ...failed,
      failure: { ...failed.failure, attempts: 3, exhausted: true },
    })

    expect(screen.queryByLabelText("Retry FPT")).not.toBeInTheDocument()
    expect(screen.getByText(/Đã thử 3\/3 lượt/)).toBeInTheDocument()
  })

  it("keeps the reason after a retry queues it, as the previous attempt's", () => {
    // Nothing drains the queue until the pipeline milestone, so a retried
    // symbol waits at `pending` for a while. Dropping the reason there would
    // leave it waiting with no account of why; keeping it red would claim
    // something is wrong right now.
    row({ ...failed, state: "pending" })

    expect(screen.getByText(/Lượt trước: .*chưa có dữ liệu thị trường/i)).toBeInTheDocument()
    expect(screen.queryByLabelText("Retry FPT")).not.toBeInTheDocument()
  })

  it("falls back to the reason the API sent when it does not know the code", () => {
    row({
      ...failed,
      failure: { ...failed.failure, code: "a_code_this_screen_has_not_learned" },
    })

    expect(screen.getByText("no session data for FPT")).toBeInTheDocument()
  })
})

describe("adding a symbol", () => {
  it("normalises what was typed and hands the symbol up", () => {
    const onAdd = vi.fn()
    render(<AddSymbolForm onAdd={onAdd} />)

    fireEvent.change(screen.getByLabelText("Add symbol"), { target: { value: " fpt " } })
    fireEvent.submit(screen.getByLabelText("Add symbol").closest("form")!)

    expect(onAdd).toHaveBeenCalledWith("FPT")
  })

  it("separates a refusal from a notice about an addition that succeeded", () => {
    // Above the allowance the symbol *is* on the Watchlist and only its Analysis
    // waits. Rendering that as an error would tell the user their addition
    // failed when it did not.
    render(
      <AddSymbolForm
        onAdd={vi.fn()}
        notice="Bạn đã dùng hết 3 lượt dựng Analysis theo yêu cầu cho phiên 12/08."
      />,
    )

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(/đã dùng hết 3 lượt/i)
  })

  it("shows a refusal as an error", () => {
    render(
      <AddSymbolForm onAdd={vi.fn()} error="Watchlist đã đủ 10 mã. Gỡ một mã trước." />,
    )

    expect(screen.getByRole("alert")).toHaveTextContent(/Watchlist đã đủ 10 mã/)
  })

  it("says nothing about a free addition", () => {
    // A symbol whose Analysis already exists costs nothing. The rail already
    // shows its state; a notice would be noise on the common path.
    expect(onDemandSentence("already_analysed", null)).toBeNull()
    expect(onDemandSentence("created", null)).toBeNull()
  })
})

describe("where the rail can be mounted", () => {
  it("claims no height of its own, so it can later be a compact dock", () => {
    const { container } = render(
      <RailHeader tradingDay={SESSION} count={1} cap={10} className="test-header" />,
    )
    const { container: entryContainer } = row()

    for (const root of [container.firstElementChild, entryContainer.firstElementChild]) {
      expect(root?.className).not.toMatch(/\bh-full\b|\bh-screen\b|\bmin-h-screen\b/)
    }
  })
})
