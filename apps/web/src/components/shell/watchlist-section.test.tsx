// @vitest-environment jsdom
/**
 * What a Watchlist row says about its Analysis without being asked.
 *
 * The row is one line, so the state travels as a dot whose accessible name is
 * the sentence. That makes the assertion here the same one a screen reader
 * makes: not "is there a grey circle" but "does it say which of the two waits
 * this is".
 *
 * The rail, the price board and the shell are mocked at their hook boundaries;
 * the ordering and the states themselves are the backend's and are tested
 * there.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { Rail, RailEntry, RunFailure } from "@/lib/alpha"

const rail = { data: undefined as Rail | undefined, isPending: false }
const add = {
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null as Error | null,
}

vi.mock("@/hooks/use-watchlist-rail", () => ({
  useWatchlistRail: () => rail,
  useRailMutations: () => ({
    add,
    remove: { mutate: vi.fn() },
  }),
}))

vi.mock("@/hooks/use-price-board", () => ({
  usePriceBoard: () => ({ data: undefined }),
  indexBySymbol: () => new Map(),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined, isPending: false }),
}))

vi.mock("./shell-state", () => ({
  useShell: () => ({ state: { contextSymbol: null }, dispatch: vi.fn() }),
}))

import { WatchlistSection } from "./watchlist-section"

function failure(code: string): RunFailure {
  return { code, message: null, attempts: 1, max_attempts: 3, exhausted: false }
}

function entry(overrides: Partial<RailEntry> = {}): RailEntry {
  return {
    symbol: "ACB",
    state: "pending",
    added_at: "2026-08-12T02:00:00Z",
    latest: null,
    failure: null,
    unread: false,
    last_seen_analysis_date: null,
    ...overrides,
  }
}

function seat(entries: RailEntry[], tradingDay: string | null = "2026-08-12") {
  rail.data = { cap: 30, count: entries.length, trading_day: tradingDay, entries }
}

afterEach(cleanup)

beforeEach(() => {
  rail.data = undefined
  rail.isPending = false
  add.mutate.mockReset()
  add.isPending = false
  add.isError = false
  add.error = null
})

/** Open the add field and type a code into it, as a user does. */
function typeCode(code: string) {
  fireEvent.click(screen.getByRole("button", { name: "Thêm mã" }))
  fireEvent.change(screen.getByLabelText("Tìm mã để thêm vào danh sách theo dõi"), {
    target: { value: code },
  })
}

describe("WatchlistSection", () => {
  it("says the Collector is being waited on, not that the symbol is queued", () => {
    seat([entry({ failure: failure("missing_market_snapshot") })])
    render(<WatchlistSection />)

    expect(
      screen.getByRole("img", { name: "Đang chờ dữ liệu phiên 12/08 về cho mã này." }),
    ).toBeTruthy()
  })

  it("says queued when nothing is being waited on", () => {
    seat([entry()])
    render(<WatchlistSection />)

    expect(
      screen.getByRole("img", { name: "Chưa tới lượt dựng Analysis cho phiên 12/08." }),
    ).toBeTruthy()
  })

  it("gives every row a sentence, including the healthy one", () => {
    seat([entry({ symbol: "FPT", state: "ready" }), entry({ symbol: "HPG", state: "failed" })])
    render(<WatchlistSection />)

    expect(screen.getByRole("img", { name: "Đã có Analysis cho phiên 12/08." })).toBeTruthy()
    expect(screen.getByRole("img", { name: "Chưa có Analysis cho phiên 12/08." })).toBeTruthy()
  })

  it("names no session when none has closed yet", () => {
    seat([entry({ failure: failure("missing_market_snapshot") })], null)
    render(<WatchlistSection />)

    expect(
      screen.getByRole("img", {
        name: "Chưa có phiên nào chốt dữ liệu nên chưa dựng Analysis.",
      }),
    ).toBeTruthy()
  })

  it("adds the typed code when the field is submitted", () => {
    seat([])
    render(<WatchlistSection />)
    typeCode("stb")

    fireEvent.click(screen.getByRole("button", { name: "Thêm mã đang gõ" }))

    expect(add.mutate).toHaveBeenCalledWith("STB", expect.anything())
  })

  it("keeps the typed code until the add succeeds", () => {
    seat([])
    render(<WatchlistSection />)
    typeCode("stb")

    fireEvent.click(screen.getByRole("button", { name: "Thêm mã đang gõ" }))

    // The mutation is still open, so nothing has succeeded: an emptied field
    // here would leave a refusal describing a code the user can no longer see.
    expect(
      screen.getByLabelText<HTMLInputElement>("Tìm mã để thêm vào danh sách theo dõi").value,
    ).toBe("stb")
  })

  it("reports the wait while the add is in flight", () => {
    seat([])
    add.isPending = true
    render(<WatchlistSection />)
    fireEvent.click(screen.getByRole("button", { name: "Thêm mã" }))

    expect(screen.getByRole("button", { name: "Đang thêm mã" })).toBeTruthy()
    expect(
      screen.getByLabelText<HTMLInputElement>("Tìm mã để thêm vào danh sách theo dõi").disabled,
    ).toBe(true)
  })
})
