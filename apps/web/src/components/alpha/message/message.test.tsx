// @vitest-environment jsdom
/**
 * What one answer promises, and what it must never do.
 *
 * Every claim here is one a plausible implementation gets wrong by being
 * conventional: a chat UI types characters out, replaces a stopped request with
 * an error page, and labels its spinner with the function it is calling. Each
 * of those is a decision this product made in the other direction.
 *
 * These components render *content*, so they are tested on their own — the
 * shell that arranges them is checked separately, and mixing the two would mean
 * mocking three query hooks to assert on a Risk Notice.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { AssistantView, DraftEntry } from "@/lib/alpha-desk/transcript"
import type { Citation, ContentBlock, RiskNotice } from "@/lib/alpha-desk/types"
import { ActivityTrail } from "./activity-line"
import { AssistantMessage } from "./assistant-message"
import { DraftMessage } from "./draft-message"

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
  // The enum values the backend sends, not prose: they exist so a translation
  // can be checked against a required set, and they are never displayed.
  meanings: ["analytical_purpose", "no_personal_advice"],
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
    source: "registered_field",
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
    steps: [],
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

describe("how an answer arrives", () => {
  it("labels an unverified prose figure without hiding its block", () => {
    render(
      <AssistantMessage
        view={view({
          blocks: [
            {
              ...block("Chủ tịch được bổ nhiệm năm 2024."),
              unverified_figures: ["2024"],
            },
          ],
        })}
      />,
    )

    expect(screen.getByText("Chủ tịch được bổ nhiệm năm 2024.")).toBeInTheDocument()
    expect(screen.getByRole("note")).toHaveTextContent("Số liệu chưa kiểm chứng")
    expect(screen.getByRole("note")).toHaveTextContent("2024")
  })

  it("names an external source and when it was retrieved", () => {
    render(
      <AssistantMessage
        view={view({
          blocks: [
            block("Ban lãnh đạo hiện tại.", [
              citation({
                source: "external_claim",
                provenance: "HOSE",
                as_of: "2026-08-17T08:00:00+07:00",
              }),
            ]),
          ],
        })}
      />,
    )

    expect(screen.getAllByText(/HOSE/).length).toBeGreaterThan(0)
    expect(screen.getByText("Nguồn ngoài · chưa kiểm chứng")).toBeInTheDocument()
    expect(screen.getAllByText(/retrieved 2026-08-17/).length).toBeGreaterThan(0)
  })

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

describe("the activity trail", () => {
  it("shows a generic phase while tools run", () => {
    render(<ActivityTrail steps={[]} phase="reading_data" />)

    expect(screen.getByRole("status")).toHaveTextContent(/Đang đọc dữ liệu/)
  })

  it("keeps the steps it finished, in the order it finished them", () => {
    render(<ActivityTrail steps={["searching", "reading_data"]} phase="analyzing" />)

    const lines = screen.getAllByRole("button").map((row) => row.textContent)
    expect(lines[0]).toMatch(/Đã tìm/)
    expect(lines[1]).toMatch(/Đã đọc dữ liệu/)
    expect(lines[2]).toMatch(/Đang phân tích/)
  })

  it("announces only the step in flight", () => {
    // A finished step is not progress. Announcing each one would turn a quiet
    // answer into a queue of interruptions for a screen reader.
    const { container } = render(
      <ActivityTrail steps={["searching", "reading_data"]} phase="analyzing" />,
    )

    expect(container.querySelectorAll("[role='status']")).toHaveLength(1)
  })

  it("draws nothing at all when there is no work to show", () => {
    const { container } = render(<ActivityTrail steps={[]} phase={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it("exposes no tool name, symbol, argument or result — collapsed or expanded", () => {
    const { container } = render(
      <ActivityTrail steps={["reading_data", "analyzing"]} phase="searching" />,
    )

    for (const row of screen.getAllByRole("button")) fireEvent.click(row)

    const markup = container.innerHTML
    for (const name of TOOL_NAMES) expect(markup).not.toContain(name)
    // No ticker, no figure: either would mean a line was assembled from a call
    // rather than from the phase the publisher named.
    expect(container.textContent).not.toMatch(/\b[A-Z]{3}\b/)
    expect(container.textContent).not.toMatch(/\d/)
  })
})

describe("the Risk Notice", () => {
  // Still attached by the backend and still parsed into the view; simply not a
  // thing this surface draws. The assertions are that it stays off screen —
  // both the canonical wording and the renderer's own fallback.
  it("is not rendered on a completed assistant message", () => {
    render(<AssistantMessage view={view()} />)

    expect(screen.queryByLabelText("Risk notice")).not.toBeInTheDocument()
    expect(screen.queryByText(NOTICE.text)).not.toBeInTheDocument()
  })

  it("puts no stand-in on screen when the message carries none", () => {
    render(<AssistantMessage view={view({ riskNotice: null })} />)

    expect(screen.queryByLabelText("Risk notice")).not.toBeInTheDocument()
    expect(screen.queryByText(/Chưa đọc được Risk Notice/)).not.toBeInTheDocument()
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

  it("explains itself in a sentence and never with the stable reason", () => {
    render(
      <DraftMessage
        entry={draft({
          phase: "incomplete",
          terminalReason: "grounding_failed",
          blocks: [block("x")],
        })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.queryByText(/grounding_failed/)).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(/không dẫn được về số liệu/)
  })

  it("keeps every block already received when it is cancelled", () => {
    render(
      <DraftMessage
        entry={draft({
          phase: "cancelling",
          blocks: [block("giữ lại"), block("và cái này")],
        })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("giữ lại")).toBeInTheDocument()
    expect(screen.getByText("và cái này")).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(/Cancelling/)
  })

  it("never becomes a full-screen error", () => {
    // The status is an inline note under the answer. Nothing takes the place of
    // what was already said, and nothing shouts.
    render(
      <DraftMessage
        entry={draft({
          phase: "failed",
          terminalReason: "route_error",
          blocks: [block("một phần")],
        })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("một phần")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})
