// @vitest-environment jsdom
/**
 * What the Alpha Desk surface promises, and what it must never do.
 *
 * Every claim here is one a plausible implementation gets wrong by being
 * conventional: a chat UI types characters out, replaces a failed request with
 * an error page, shows a spinner labelled with the function it is calling, and
 * disables the input while it is busy. Each of those is a decision this product
 * made in the other direction, and each is checked below.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"

import type { AssistantView, DraftEntry, TranscriptEntry } from "@/lib/alpha-desk/transcript"
import type { Citation, ContentBlock, RiskNotice } from "@/lib/alpha-desk/types"
import { ActivityLine } from "./activity-line"
import { AssistantMessage } from "./assistant-message"
import { Composer } from "./composer"
import { DeskSurface } from "./desk-surface"
import { DraftMessage } from "./draft-message"
import { SymbolDock } from "./symbol-dock"

afterEach(cleanup)

// The v1 catalog. Named here because the point is that none of these names has
// any route to the browser.
const TOOL_NAMES = [
  "get_analysis",
  "get_company_profile",
  "get_financials",
  "get_price_series",
  "get_watchlist",
  "screen_universe",
  "search_news",
]

const NOTICE: RiskNotice = {
  version: "risk-notice/1",
  locale: "vi",
  text: "Đây không phải khuyến nghị đầu tư.",
  meanings: ["Không đảm bảo lợi nhuận."],
}

function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    tool_call_id: "call_01",
    tool_name: "get_analysis",
    field_path: "technical.momentum_273d",
    value: 12.4,
    unit: "%",
    interpretation: "Cao hơn trung vị ngành.",
    claim: null,
    provenance: "registry",
    as_of: "2026-08-14",
    stale: false,
    source: "computed",
    window_health: null,
    contradictory: false,
    zone_label: null,
    reference_price: false,
    ...overrides,
  }
}

function block(text: string, citations: Citation[] = []): ContentBlock {
  return { kind: "prose", text, symbol: null, trading_day: null, citations }
}

function draft(overrides: Partial<DraftEntry> = {}): DraftEntry {
  return {
    kind: "draft",
    key: "draft-1",
    blocks: [],
    activity: null,
    phase: "running",
    terminalReason: null,
    appendedIndex: null,
    ...overrides,
  }
}

function view(overrides: Partial<AssistantView> = {}): AssistantView {
  return {
    blocks: [block("kết luận")],
    riskNotice: NOTICE,
    sourcesAndMethods: [],
    ...overrides,
  }
}

function surface(overrides: Partial<React.ComponentProps<typeof DeskSurface>> = {}) {
  return render(
    <DeskSurface
      dock={<div data-testid="dock" />}
      entries={[]}
      activeSymbol={null}
      canCancel={false}
      isCancelling={false}
      isSubmitting={false}
      refusal={null}
      onSend={vi.fn()}
      onCancel={vi.fn()}
      onRetry={vi.fn()}
      onDismissRefusal={vi.fn()}
      {...overrides}
    />,
  )
}

describe("how an answer arrives", () => {
  it("shows a block whole, with a fade rather than a typewriter", () => {
    // The backend buffers deltas into Markdown-safe units, so the block is
    // complete when it lands. Revealing it letter by letter would put back an
    // illusion the transport was built to remove.
    const { container } = render(
      <DraftMessage
        entry={draft({ blocks: [block("một câu đầy đủ")], appendedIndex: 0 })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("một câu đầy đủ")).toBeInTheDocument()
    expect(container.querySelector(".transition-opacity")).not.toBeNull()
  })

  it("removes the transition entirely under reduced motion", () => {
    const { container } = render(
      <DraftMessage
        entry={draft({ blocks: [block("một")], appendedIndex: 0 })}
        onRetry={vi.fn()}
      />,
    )

    const revealed = container.querySelector(".transition-opacity")
    expect(revealed?.className).toContain("motion-reduce:transition-none")
    expect(revealed?.className).toContain("motion-reduce:opacity-100")
  })

  it("renders a reopened Thread all at once, with no staged replay", () => {
    // A null `appendedIndex` means a snapshot replaced the projection rather
    // than an event delivering one block. Nothing carries transition markup at
    // all, so "at once" is visible in the DOM rather than a matter of how long
    // the test waits.
    const { container } = render(
      <DraftMessage
        entry={draft({ blocks: [block("một"), block("hai"), block("ba")] })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("ba")).toBeInTheDocument()
    expect(container.querySelector(".transition-opacity")).toBeNull()
  })
})

describe("the activity line", () => {
  it("shows a generic phase while tools run", () => {
    render(<ActivityLine phase="reading_data" />)

    expect(screen.getByRole("status")).toHaveTextContent(/Đang đọc dữ liệu/)
  })

  it("exposes no tool name, symbol, argument or result — collapsed or expanded", () => {
    const { container } = render(<ActivityLine phase="searching" />)

    fireEvent.click(screen.getByText("Details"))

    const markup = container.innerHTML
    for (const name of TOOL_NAMES) expect(markup).not.toContain(name)
    // No ticker, no figure: either would mean the line was assembled from a
    // call rather than from the phase the publisher named.
    expect(container.textContent).not.toMatch(/\b[A-Z]{3}\b/)
    expect(container.textContent).not.toMatch(/\d/)
  })

  it("is one line and not a running list of steps", () => {
    const { container } = render(<ActivityLine phase="analyzing" />)

    expect(container.querySelectorAll("[role='status']")).toHaveLength(1)
  })
})

describe("the Risk Notice", () => {
  it("renders on a completed assistant message", () => {
    render(<AssistantMessage view={view()} />)

    expect(screen.getByLabelText("Risk notice")).toHaveTextContent(
      /không phải khuyến nghị đầu tư/i,
    )
  })

  it("renders on a usefully incomplete one too", () => {
    // An incomplete Turn with content writes a canonical message like any
    // other, and the notice is exactly as owed there.
    render(<AssistantMessage view={view({ blocks: [block("một phần")] })} />)

    expect(screen.getByLabelText("Risk notice")).toBeInTheDocument()
  })

  it("is displayed by the renderer, so model prose cannot stand in for it", () => {
    // The notice element is present even for a message that carries none, and
    // its fallback is the renderer's own voice rather than a copy of the
    // canonical wording.
    render(<AssistantMessage view={view({ riskNotice: null })} />)

    const notice = screen.getByLabelText("Risk notice")
    expect(notice).toHaveTextContent(/Chưa đọc được Risk Notice/)
    expect(notice).not.toHaveTextContent(NOTICE.text)
  })
})

describe("what an answer never shows", () => {
  it("names no tool, anywhere, even where a citation carries one", () => {
    const { container } = render(
      <AssistantMessage
        view={view({
          blocks: [block("kết luận", [citation()])],
          sourcesAndMethods: [
            {
              provider_source: "vnstock",
              tool_call_id: "call_01",
              tool_name: "get_price_series",
              registered_field: "technical.momentum_273d",
              value: 12.4,
              unit: "%",
              interpretation: "Cao hơn trung vị ngành.",
              freshness: { as_of: "2026-08-14", stale: false },
              window_health: null,
            },
          ],
        })}
      />,
    )

    fireEvent.click(screen.getByText("View details"))
    fireEvent.click(screen.getByText("Sources & methods"))

    const markup = container.innerHTML
    for (const name of TOOL_NAMES) expect(markup).not.toContain(name)
    expect(markup).not.toContain("call_01")
  })

  it("puts the unit and the as_of beside the figure rather than behind a disclosure", () => {
    render(<AssistantMessage view={view({ blocks: [block("kết luận", [citation()])] })} />)

    expect(screen.getByText("12,4")).toBeInTheDocument()
    expect(screen.getByText("%")).toBeInTheDocument()
    expect(screen.getByText("as of 2026-08-14")).toBeInTheDocument()
  })

  it("keeps method detail behind View details", () => {
    render(<AssistantMessage view={view({ blocks: [block("kết luận", [citation()])] })} />)

    expect(screen.queryByText("technical.momentum_273d")).not.toBeInTheDocument()

    fireEvent.click(screen.getByText("View details"))

    expect(screen.getByText("technical.momentum_273d")).toBeInTheDocument()
  })
})

describe("cancelling", () => {
  it("says Cancelling… and disables the control the moment it is pressed", () => {
    const onCancel = vi.fn()
    const { rerender } = render(
      <Composer
        onSend={vi.fn()}
        onCancel={onCancel}
        canCancel
        isCancelling={false}
        isSubmitting={false}
        activeSymbol={null}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /stop/i }))
    expect(onCancel).toHaveBeenCalledOnce()

    rerender(
      <Composer
        onSend={vi.fn()}
        onCancel={onCancel}
        canCancel
        isCancelling
        isSubmitting={false}
        activeSymbol={null}
      />,
    )

    const stop = screen.getByRole("button", { name: /cancelling/i })
    expect(stop).toBeDisabled()
  })

  it("keeps every block already received", () => {
    render(
      <DraftMessage
        entry={draft({ phase: "cancelling", blocks: [block("giữ lại"), block("và cái này")] })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("giữ lại")).toBeInTheDocument()
    expect(screen.getByText("và cái này")).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(/Cancelling/)
  })
})

describe("a Turn that stopped early", () => {
  it("keeps its useful content and offers a retry beside it", () => {
    render(
      <DraftMessage
        entry={draft({
          phase: "incomplete",
          terminalReason: "turn_deadline",
          blocks: [block("phần đã trả lời được")],
        })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("phần đã trả lời được")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("never replaces that content with a full-screen error", () => {
    // The status is an inline note under the answer. Nothing takes the place of
    // the transcript, and nothing shouts.
    const entries: TranscriptEntry[] = [
      { kind: "user", key: "u1", text: "FPT thế nào?", pending: false },
      draft({ phase: "failed", terminalReason: "route_error", blocks: [block("một phần") ] }),
    ]
    surface({ entries, })

    expect(screen.getByText("một phần")).toBeInTheDocument()
    expect(screen.getByText("FPT thế nào?")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("explains itself in a sentence and never with the stable reason", () => {
    render(
      <DraftMessage
        entry={draft({ phase: "incomplete", terminalReason: "grounding_failed", blocks: [block("x")] })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.queryByText(/grounding_failed/)).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(/không dẫn được về số liệu/)
  })

  it("starts a new Turn on retry and leaves the previous one on screen", () => {
    const onRetry = vi.fn()
    const entries: TranscriptEntry[] = [
      { kind: "assistant", key: "m1", messageId: 1, view: view({ blocks: [block("lượt trước") ] }), flaggedReason: null },
      draft({ phase: "incomplete", terminalReason: "turn_deadline", blocks: [block("lượt này") ] }),
    ]
    surface({ entries, onRetry })

    fireEvent.click(screen.getByRole("button", { name: /retry/i }))

    expect(onRetry).toHaveBeenCalledOnce()
    // Retry creates a Turn; it does not edit one. The earlier answer is
    // untouched and still readable.
    expect(screen.getByText("lượt trước")).toBeInTheDocument()
    expect(screen.getByText("lượt này")).toBeInTheDocument()
  })
})

describe("the first run", () => {
  it("states the Universe-vs-Watchlist rule and the scope boundary", () => {
    surface({ entries: [] })

    expect(screen.getByText(/bất kỳ mã nào trong Universe/)).toBeInTheDocument()
    expect(screen.getByText(/không tính toán tuỳ ý/)).toBeInTheDocument()
  })

  it("publishes no catalog", () => {
    const { container } = surface({ entries: [] })

    for (const name of TOOL_NAMES) expect(container.innerHTML).not.toContain(name)
  })
})

describe("the dock", () => {
  it("changes the lens without touching the Thread", () => {
    // Switching symbols changes the Analysis context and nothing else. The dock
    // has one callback and it carries a symbol.
    const onSelect = vi.fn()
    render(
      <SymbolDock
        symbols={[{
          symbol: "FPT",
          state: "ready",
          verdict: "hold",
          unread: false,
          latestTradingDay: "2026-08-14",
        }]}
        activeSymbol={null}
        onSelect={onSelect}
        onOpenAnalysis={vi.fn()}
        tradingDay="2026-08-14"
        count={1}
        cap={10}
      >
        <div />
      </SymbolDock>,
    )

    // The chip, not the control beside it: opening an Analysis is a different
    // act from changing the lens and must not be reachable by the same click.
    fireEvent.click(screen.getByRole("button", { name: /hold/ }))

    expect(onSelect).toHaveBeenCalledWith("FPT")
  })

  it("opens one specific Analysis, by symbol and by session", () => {
    const onOpenAnalysis = vi.fn()
    const onSelect = vi.fn()
    render(
      <SymbolDock
        symbols={[{
          symbol: "FPT",
          state: "ready",
          verdict: "hold",
          unread: true,
          latestTradingDay: "2026-08-14",
        }]}
        activeSymbol={null}
        onSelect={onSelect}
        onOpenAnalysis={onOpenAnalysis}
        tradingDay="2026-08-14"
        count={1}
        cap={10}
      >
        <div />
      </SymbolDock>,
    )

    fireEvent.click(screen.getByRole("button", { name: "Open FPT Analysis" }))

    expect(onOpenAnalysis).toHaveBeenCalledWith("FPT", "2026-08-14")
    // The badge advances because *this* Analysis was opened. Changing the lens
    // would clear ten badges at once, so the two controls stay apart.
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("offers nothing to open for a symbol that has never been analysed", () => {
    render(
      <SymbolDock
        symbols={[{
          symbol: "TCX",
          state: "pending",
          verdict: null,
          unread: false,
          latestTradingDay: null,
        }]}
        activeSymbol={null}
        onSelect={vi.fn()}
        onOpenAnalysis={vi.fn()}
        tradingDay="2026-08-14"
        count={1}
        cap={10}
      >
        <div />
      </SymbolDock>,
    )

    expect(screen.queryByRole("button", { name: /Open TCX Analysis/ })).toBeNull()
  })

  it("shows a deep-linked symbol as a lens that is not on the Watchlist", () => {
    render(
      <SymbolDock
        symbols={[{
          symbol: "FPT",
          state: "ready",
          verdict: "hold",
          unread: false,
          latestTradingDay: "2026-08-14",
        }]}
        activeSymbol="HPG"
        onSelect={vi.fn()}
        onOpenAnalysis={vi.fn()}
        tradingDay="2026-08-14"
        count={1}
        cap={10}
      >
        <div />
      </SymbolDock>,
    )

    const chips = screen.getByLabelText("Symbols")
    expect(within(chips).getByText("HPG")).toBeInTheDocument()
    expect(within(chips).getByText(/ngoài Watchlist/)).toBeInTheDocument()
  })

  it("scrolls its own chips rather than widening the page", () => {
    const { container } = render(
      <SymbolDock
        symbols={[]}
        activeSymbol={null}
        onSelect={vi.fn()}
        onOpenAnalysis={vi.fn()}
        tradingDay={null}
        count={0}
        cap={10}
      >
        <div />
      </SymbolDock>,
    )

    const scroller = container.querySelector(".overflow-x-auto")
    expect(scroller).not.toBeNull()
    // Without `min-w-0` the chip list sizes to its content and the page body
    // gains the scrollbar instead of the dock.
    expect(scroller?.className).toContain("min-w-0")
  })
})

describe("the composer", () => {
  it("stays usable while an on-demand Analysis is producing", () => {
    const onSend = vi.fn()
    surface({
      onSend,
      dock: (
        <SymbolDock
          symbols={[{
              symbol: "FPT",
              state: "producing",
              verdict: null,
              unread: false,
              latestTradingDay: null,
            }]}
          activeSymbol="FPT"
          onSelect={vi.fn()}
          onOpenAnalysis={vi.fn()}
          tradingDay="2026-08-14"
          count={1}
          cap={10}
        >
          <div />
        </SymbolDock>
      ),
    })

    const field = screen.getByLabelText("Ask Alpha Desk")
    expect(field).not.toBeDisabled()

    fireEvent.change(field, { target: { value: "vì sao?" } })
    fireEvent.submit(field.closest("form")!)

    expect(onSend).toHaveBeenCalledWith("vì sao?")
  })

  it("keeps the field open while a Turn is running, and offers Stop instead of Send", () => {
    surface({ canCancel: true })

    expect(screen.getByLabelText("Ask Alpha Desk")).not.toBeDisabled()
    expect(screen.queryByRole("button", { name: /^send$/i })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument()
  })
})

describe("an admission refusal", () => {
  it("is shown as its own sentence, beside the transcript rather than over it", () => {
    // A 429 or a 503 is an HTTP outcome carrying a stable reason, never an
    // event, and never a reason to clear what is on screen.
    const entries: TranscriptEntry[] = [
      { kind: "assistant", key: "m1", messageId: 1, view: view(), flaggedReason: null },
    ]
    surface({ entries, refusal: "Bạn đang có một lượt đang chạy." })

    expect(screen.getByRole("alert")).toHaveTextContent(/một lượt đang chạy/)
    expect(screen.getByText("kết luận")).toBeInTheDocument()
  })
})

describe("the shell", () => {
  it("pins itself to one viewport and gives the transcript its own scroll", () => {
    const { container } = surface({
      entries: [{ kind: "user", key: "u1", text: "hỏi", pending: false }],
    })

    const root = container.firstElementChild
    expect(root?.className).toMatch(/\bh-full\b/)
    expect(root?.className).toMatch(/overflow-hidden/)

    const scroller = container.querySelector(".overflow-y-auto")
    expect(scroller).not.toBeNull()
    expect(scroller?.textContent).toContain("hỏi")
  })

  it("never lets the page body scroll horizontally", () => {
    const { container } = surface({
      entries: [{ kind: "user", key: "u1", text: "hỏi", pending: false }],
    })

    // Nothing in the tree may scroll the page sideways: the dock owns the one
    // horizontal scroller, and it is not this.
    for (const element of container.querySelectorAll("div")) {
      expect(element.className).not.toMatch(/\boverflow-x-scroll\b/)
    }
    expect(container.firstElementChild?.className).toMatch(/\bw-full\b/)
  })
})
