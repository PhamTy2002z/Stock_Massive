// @vitest-environment jsdom
/**
 * What Settings offers, and what it refuses to pretend.
 *
 * The dialog used to hold one working control and four read-only values, two of
 * which were compile-time constants dressed as fields. Two properties are worth
 * a test:
 *
 * *An allowance is drawn in the state it is actually in.* Loading, unlimited and
 * metered are three different facts. Drawing an unlimited ceiling as a full
 * meter would tell a reader on a subscription route that they had run out of
 * something they cannot run out of — and every ceiling is unlimited on that
 * route, so it is the default case there rather than an edge.
 *
 * *A default is a default, not a switch.* The Hội thoại pane answers what a new
 * conversation opens with. It must write the preference and nothing else; the
 * per-conversation mode stays on the composer.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"

import type { Usage } from "@/lib/alpha-desk/types"

const fetchUsage = vi.fn<() => Promise<Usage>>()

vi.mock("@/lib/alpha-desk/api", () => ({ fetchUsage: () => fetchUsage() }))
vi.mock("./shell-state", () => ({ useShell: () => ({ dispatch: () => {} }) }))
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    user: { email: "nha.dautu@example.com", full_name: "Nhà đầu tư" },
    isPending: false,
  }),
}))

import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

import { SettingsDialog } from "./settings-dialog"

function allowance(used: number, limit: number | null, resetsAt: string | null = null) {
  return { used, limit, resets_at: resetsAt }
}

function usage(overrides: Partial<Usage> = {}): Usage {
  return {
    as_of: "2026-08-28T08:00:00Z",
    turns_today: allowance(0, 20),
    spend_today_micro_usd: allowance(0, 3_000_000),
    spend_rolling_30d_micro_usd: allowance(0, 15_000_000),
    ...overrides,
  }
}

function open() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <SettingsDialog />
    </QueryClientProvider>,
  )
}

/** Move the rail to a pane by its label, the way a reader does. */
function goTo(label: string) {
  fireEvent.click(screen.getByRole("button", { name: label }))
}

beforeEach(() => {
  fetchUsage.mockReset()
  fetchUsage.mockResolvedValue(usage())
})

afterEach(cleanup)

describe("the rail", () => {
  it("offers the four panes that have something to do", () => {
    open()

    for (const label of ["Giao diện", "Hội thoại", "Hồ sơ", "Hạn mức"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument()
    }
  })

  it("no longer offers a pane of compile-time constants", () => {
    open()

    // The display timezone and the exchange list moved to where the numbers
    // are, which is the provenance strip under each Signal Desk.
    expect(screen.queryByRole("button", { name: "Hệ thống" })).toBeNull()
  })

  it("filters to nothing rather than showing a stale pane", () => {
    open()

    fireEvent.change(screen.getByLabelText("Tìm cài đặt"), {
      target: { value: "không có mục nào như vậy" },
    })

    expect(screen.getByText("Không có mục nào khớp.")).toBeInTheDocument()
  })
})

describe("the allowance", () => {
  it("draws a metered ceiling with what is left", async () => {
    fetchUsage.mockResolvedValue(usage({ turns_today: allowance(7, 20) }))
    open()
    goTo("Hạn mức")

    const meter = await screen.findByRole("meter", { name: /Câu hỏi hôm nay/ })

    expect(meter).toHaveAttribute("aria-valuenow", "7")
    expect(meter).toHaveAttribute("aria-valuemax", "20")
    expect(screen.getByText("Còn 13")).toBeInTheDocument()
  })

  it("says unlimited rather than drawing a meter against nothing", async () => {
    // Every ceiling is null on a subscription route, so this is that route's
    // ordinary case.
    fetchUsage.mockResolvedValue(usage({ turns_today: allowance(41, null) }))
    open()
    goTo("Hạn mức")

    expect(await screen.findByText("41 · không giới hạn")).toBeInTheDocument()
    expect(screen.queryByRole("meter", { name: /Câu hỏi hôm nay/ })).toBeNull()
  })

  it("says when a spent allowance frees rather than only that it is spent", async () => {
    fetchUsage.mockResolvedValue(
      usage({ turns_today: allowance(20, 20, "2026-08-28T17:00:00Z") }),
    )
    open()
    goTo("Hạn mức")

    // 17:00Z is midnight in Ho Chi Minh City, which is the reset the API means.
    expect(await screen.findByText(/Đã dùng hết · mở lại/)).toBeInTheDocument()
  })

  it("does not round a real charge down to nothing", async () => {
    fetchUsage.mockResolvedValue({
      ...usage(),
      spend_today_micro_usd: allowance(4_000, 3_000_000),
    })
    open()
    goTo("Hạn mức")

    // $0.004 spent. "$0.00" beside a meter that has moved reads as broken.
    expect(await screen.findByText(/<\$0,01/)).toBeInTheDocument()
  })

  it("offers a retry rather than an empty panel when the read fails", async () => {
    fetchUsage.mockRejectedValue(new Error("upstream is down"))
    open()
    goTo("Hạn mức")

    expect(
      await screen.findByRole("button", { name: "Thử lại" }),
    ).toBeInTheDocument()
  })
})

describe("how a new conversation opens", () => {
  it("starts from what the browser last chose", () => {
    writePreferences({ signalDeskByDefault: true })
    open()
    goTo("Hội thoại")

    expect(screen.getByRole("radio", { name: "Signal Desk" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
  })

  it("writes the default without touching anything else", async () => {
    writePreferences({ chatWidth: 640 })
    open()
    goTo("Hội thoại")

    fireEvent.click(screen.getByRole("radio", { name: "Signal Desk" }))

    await waitFor(() => {
      expect(readPreferences().signalDeskByDefault).toBe(true)
    })
    // The shell's own remembered width is a different caller's field.
    expect(readPreferences().chatWidth).toBe(640)
  })

  it("claims nothing during the first paint, before storage has been read", () => {
    writePreferences({ signalDeskByDefault: true })
    open()
    goTo("Hội thoại")

    // Both segments unselected would be the pre-mount state. By the time the
    // rail has been clicked the effect has run, so exactly one is checked —
    // what must never happen is *both* reading as unchecked after mount.
    const checked = screen
      .getAllByRole("radio")
      .filter((radio) => radio.getAttribute("aria-checked") === "true")

    expect(checked).toHaveLength(1)
  })
})
