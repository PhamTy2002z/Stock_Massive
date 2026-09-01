// @vitest-environment jsdom
/**
 * What Settings offers, and what it refuses to pretend.
 *
 * Three properties are worth a test:
 *
 * *An allowance is drawn in the state it is actually in.* Loading, unlimited and
 * metered are three different facts. Drawing an unlimited ceiling as a full
 * meter would tell a reader on a subscription route that they had run out of
 * something they cannot run out of — and every ceiling is unlimited on that
 * route, so it is the default case there rather than an edge.
 *
 * *A default is a default, not a per-conversation switch.* The Hội thoại pane
 * answers what a new conversation opens with. It must write the preference and
 * nothing else; the per-conversation mode stays on the composer.
 *
 * *A row with nothing behind it says so.* Most of the dialog is drawn ahead of
 * the writes that would make it work, and the whole point of drawing it that way
 * is the badge and the inert control. A row that lost its badge would be a live
 * control that silently discards what the reader chose — which is the failure
 * this surface exists to avoid, so it is asserted rather than eyeballed.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"

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
  it("offers every pane in both groups", () => {
    open()

    for (const label of [
      "Giao diện",
      "Hội thoại",
      "Thông báo",
      "Hồ sơ",
      "Hạn mức",
      "Bảo mật",
      "Dữ liệu",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument()
    }
  })

  it("no longer offers a pane of compile-time constants", () => {
    open()

    // Runtime configuration is not editable from this dialog, so there is no
    // pane for it and the rail is the only place a pane can be reached from.
    const rail = screen.getByRole("navigation", { name: "Mục cài đặt" })
    const labels = Array.from(rail.querySelectorAll("button")).map(
      (button) => button.textContent,
    )

    expect(labels).not.toContain("Hệ thống")
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

describe("rows drawn ahead of their write path", () => {
  it("marks an unbuilt control rather than letting it look live", () => {
    open()
    goTo("Bảo mật")

    const twoFactor = screen.getByRole("switch", { name: "Xác thực hai bước" })

    expect(twoFactor).toBeDisabled()
    // The badge is the row's own promise, so it has to be beside this label
    // rather than merely somewhere on the pane.
    expect(
      twoFactor.closest("div")?.parentElement?.textContent,
    ).toContain("Sắp ra mắt")
  })

  it("keeps the account's real email readable on the pane that holds it", () => {
    open()
    goTo("Bảo mật")

    // Scoped to the pane: the same address is also on the rail's account card,
    // which is a different claim about a different surface.
    const pane = screen.getByRole("region", { name: "Bảo mật" })

    expect(within(pane).getByText("nha.dautu@example.com")).toBeInTheDocument()
  })
})
