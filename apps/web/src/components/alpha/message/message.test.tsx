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
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitForElementToBeRemoved,
} from "@testing-library/react"

import type { AssistantView, DraftEntry } from "@/lib/alpha-desk/transcript"
import type { Citation, ContentBlock, RiskNotice } from "@/lib/alpha-desk/types"
import { AssistantMessage } from "./assistant-message"
import { DraftMessage } from "./draft-message"
import { SearchProgress } from "./search-progress"

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
    searchProgress: [],
    suggestions: [],
    completed: true,
    ...overrides,
  }
}

describe("how an answer arrives", () => {
  it("keeps an unverified figure's record off the answer", () => {
    // The grounding pass still records the figures it could not tie to
    // evidence — it is what withholds a recommendation — but the reader was
    // shown that record as a row of bare literals, which reads as a defect in
    // the answer rather than as provenance.
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
    expect(screen.queryByRole("note")).not.toBeInTheDocument()
    expect(screen.queryByText(/chưa kiểm chứng/)).not.toBeInTheDocument()
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

    // Behind the chip, which is where ADR-0015's first provenance layer lives
    // now: one press from the claim, and never further.
    fireEvent.click(screen.getByLabelText(/Nguồn của đoạn này/))

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

describe("the search-progress trail", () => {
  it("shows every step in order, with the running one announced", () => {
    render(
      <SearchProgress
        steps={[{ phase: "reading_data" }, { phase: "searching" }]}
        activity="searching"
        defaultOpen
      />,
    )

    const rows = screen.getAllByRole("listitem").map((row) => row.textContent)
    // A step that is over says what it did; only the live row says *Đang…*.
    expect(rows[0]).toMatch(/Đã đọc dữ liệu đã lưu/)
    expect(rows[1]).toMatch(/Đang tìm trên web/)
    // A finished step is not progress: announcing each one would turn a quiet
    // answer into a queue of interruptions for a screen reader.
    expect(screen.getAllByRole("status")).toHaveLength(1)
    expect(screen.getByRole("status")).toHaveTextContent(/Đang tìm trên web/)
  })

  it("keeps the analysis row only while it is the step happening", () => {
    // It names no query, no source and no count, so once it is over it says
    // only that the system thought about an answer already on screen.
    const { rerender } = render(
      <SearchProgress steps={[{ phase: "analyzing" }]} activity="analyzing" defaultOpen />,
    )

    expect(screen.getByText("Đang suy nghĩ…")).toBeInTheDocument()

    rerender(
      <SearchProgress
        steps={[{ phase: "analyzing" }, { phase: "searching" }]}
        activity="searching"
        defaultOpen
      />,
    )

    expect(screen.queryByText("Đang suy nghĩ…")).not.toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(1)
  })

  it("draws no trail when analysis is the only thing it could show", () => {
    // A disclosure whose one row is *Hoàn thành* discloses nothing.
    const { container } = render(
      <SearchProgress steps={[{ phase: "analyzing" }]} activity={null} ending="done" />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it("animates a step as it lands and leaves the older ones still", () => {
    // The trail is a list the reader watches grow. A step that arrived while
    // they were looking rises into place; the ones above it already did.
    const searching = { phase: "searching" as const, detail: { queries: ["tin tức AI"] } }
    const { rerender } = render(
      <SearchProgress steps={[searching]} activity="searching" defaultOpen />,
    )

    rerender(
      <SearchProgress
        steps={[searching, { phase: "found_sources", detail: { result_count: 4 } }]}
        activity="found_sources"
        defaultOpen
      />,
    )

    expect(screen.getByText("Đã tìm thấy 4 kết quả").closest("li")).toHaveClass(
      "animate-vg-row-in",
    )
    expect(screen.getByText("Đã tìm trên web").closest("li")).not.toHaveClass(
      "animate-vg-row-in",
    )
  })

  it("draws a reopened Turn's trail without replaying it", () => {
    // Every step of a finished Turn arrived before the reader opened it, so
    // animating them would stage work that ended minutes ago.
    render(
      <SearchProgress
        steps={[{ phase: "reading_data" }]}
        activity={null}
        ending="done"
        defaultOpen
      />,
    )

    expect(screen.getByText("Đã đọc dữ liệu đã lưu").closest("li")).not.toHaveClass(
      "animate-vg-row-in",
    )
    expect(screen.getByText("Hoàn thành").closest("li")).not.toHaveClass(
      "animate-vg-row-in",
    )
  })

  it("folds itself once the answer starts arriving under it", async () => {
    // The lookups stop being the thing on screen the moment the first block
    // lands; leaving the trail open across the whole stream keeps the machinery
    // above the answer it was gathered for.
    const { rerender } = render(
      <SearchProgress
        steps={[{ phase: "searching", detail: { queries: ["tin tức AI"] } }]}
        activity="searching"
        defaultOpen
      />,
    )

    expect(screen.getByText("tin tức AI")).toBeInTheDocument()

    rerender(
      <SearchProgress
        steps={[{ phase: "searching", detail: { queries: ["tin tức AI"] } }]}
        activity={null}
        answered
        defaultOpen
      />,
    )

    // The rows leave over the fold rather than in the frame the answer landed:
    // a disclosure that vanishes reads as content being taken away.
    expect(screen.getByRole("button", { name: /Tiến trình tìm kiếm/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    )
    await waitForElementToBeRemoved(() => screen.queryByText("tin tức AI"))
  })

  it("folds itself the moment the Turn ends, however it was left open", async () => {
    const { rerender } = render(
      <SearchProgress steps={[{ phase: "reading_data" }]} activity="reading_data" defaultOpen />,
    )

    expect(screen.getByText("Đang đọc dữ liệu…")).toBeInTheDocument()

    rerender(
      <SearchProgress steps={[{ phase: "reading_data" }]} activity={null} ending="done" />,
    )

    // Not waiting for the canonical message to replace the draft: between the
    // two is a gap spent reading an answer with the machinery open above it.
    expect(screen.getByRole("button", { name: /Tiến trình tìm kiếm/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    )
    await waitForElementToBeRemoved(() => screen.queryByText("Đã đọc dữ liệu đã lưu"))
  })

  it("discloses the open web's queries, its result count and its sources", () => {
    render(
      <SearchProgress
        steps={[
          { phase: "searching", detail: { queries: ["chủ tịch Masan Group"] } },
          {
            phase: "found_sources",
            detail: {
              result_count: 15,
              sources: [
                {
                  title: "Ban lãnh đạo của Công ty CP Tập đoàn Masan",
                  url: "https://masangroup.com/leadership",
                  domain: "masangroup.com",
                },
              ],
            },
          },
        ]}
        activity={null}
        ending="done"
        defaultOpen
      />,
    )

    expect(screen.getByText("chủ tịch Masan Group")).toBeInTheDocument()
    expect(screen.getByText("Đã tìm thấy 15 kết quả")).toBeInTheDocument()
    expect(screen.getByText("Tổng hợp 15 nguồn")).toBeInTheDocument()
    expect(screen.getByText("masangroup.com")).toBeInTheDocument()
    expect(screen.getByText("Hoàn thành")).toBeInTheDocument()
  })

  it("opens every source in a new tab without a referrer", () => {
    // Untrusted external pages reached from an authenticated surface: the
    // referrer would tell each host which app sent the reader.
    render(
      <SearchProgress
        steps={[
          {
            phase: "found_sources",
            detail: {
              result_count: 1,
              sources: [{ title: "Bản tin", url: "https://e.vnexpress.net/a", domain: "e.vnexpress.net" }],
            },
          },
        ]}
        activity={null}
        defaultOpen
      />,
    )

    const link = screen.getByRole("link", { name: /Bản tin/ })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("folds away by default, so a finished answer reads as an answer", () => {
    render(<SearchProgress steps={[{ phase: "reading_data" }]} activity={null} ending="done" />)

    expect(screen.queryByText("Đã đọc dữ liệu đã lưu")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /Tiến trình tìm kiếm/ }))

    expect(screen.getByText("Đã đọc dữ liệu đã lưu")).toBeInTheDocument()
  })

  it("draws nothing at all when there is no work to show", () => {
    const { container } = render(<SearchProgress steps={[]} activity={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it("exposes no tool name, symbol or figure on a store-reading step", () => {
    // ADR-0020 widened disclosure for the open web only. A step from a lane that
    // reads the store still carries a phase and nothing else.
    const { container } = render(
      <SearchProgress
        steps={[{ phase: "reading_data" }, { phase: "analyzing" }]}
        activity={null}
        ending="done"
        defaultOpen
      />,
    )

    const markup = container.innerHTML
    for (const name of TOOL_NAMES) expect(markup).not.toContain(name)
    expect(container.textContent).not.toMatch(/\b[A-Z]{3}\b/)
    expect(container.textContent).not.toMatch(/\d/)
  })
})

describe("how prose is rendered", () => {
  it("renders Markdown rather than showing its syntax", () => {
    // A block is a Markdown-safe unit by construction (ADR-0013). Showing it
    // verbatim put `**` on screen in front of readers.
    render(<AssistantMessage view={view({ blocks: [block("Chủ tịch là **ông Quang**.")] })} />)

    expect(screen.getByText("ông Quang")).toBeInTheDocument()
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument()
  })

  it("renders no HTML a block happens to contain", () => {
    // No `rehype-raw`, so there is no path from model output to markup: an
    // injected tag is escaped and reaches the reader as the text it is.
    const { container } = render(
      <AssistantMessage
        view={view({ blocks: [block('Xem <img src="x" onerror="alert(1)"> nhé.')] })}
      />,
    )

    expect(container.querySelector("img")).toBeNull()
    expect(container.textContent).toContain('<img src="x" onerror="alert(1)">')
  })
})

describe("what the answer offers underneath", () => {
  it("counts the sources behind it and lists them on demand", () => {
    render(
      <AssistantMessage
        view={view({
          searchProgress: [
            {
              phase: "found_sources",
              detail: {
                result_count: 2,
                sources: [
                  { title: "Trang A", url: "https://a.vn/1", domain: "a.vn" },
                  { title: "Trang B", url: "https://b.vn/2", domain: "b.vn" },
                ],
              },
            },
          ],
        })}
      />,
    )

    fireEvent.click(screen.getByText("2 nguồn"))

    expect(screen.getByRole("link", { name: /Trang A/ })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Trang B/ })).toBeInTheDocument()
  })

  it("opens the drawer with what each page said and when", () => {
    render(
      <AssistantMessage
        view={view({
          searchProgress: [
            {
              phase: "found_sources",
              detail: {
                result_count: 1,
                sources: [
                  {
                    title: "Ban lãnh đạo của Công ty CP Tập đoàn Masan",
                    url: "https://masangroup.com/leadership",
                    domain: "masangroup.com",
                    snippet: "Ban Điều hành gồm năm thành viên điều hành cao cấp.",
                    published_at: "2025-11-20",
                    retrieved_at: "2026-06-19T08:00:00+00:00",
                  },
                ],
              },
            },
          ],
        })}
      />,
    )

    fireEvent.click(screen.getByText("1 nguồn"))

    expect(screen.getByText("1 nguồn tham khảo")).toBeInTheDocument()
    expect(screen.getByText("masangroup.com")).toBeInTheDocument()
    expect(
      screen.getByText("Ban Điều hành gồm năm thành viên điều hành cao cấp."),
    ).toBeInTheDocument()
    // Both timestamps read as the reader's calendar, never as the wire format.
    expect(screen.getByText("20 thg 11, 2025")).toBeInTheDocument()
    expect(screen.getByText("Cập nhật: 19 thg 6, 2026")).toBeInTheDocument()
  })

  it("shows no excerpt and no dates for a page whose result offered none", () => {
    render(
      <AssistantMessage
        view={view({
          searchProgress: [
            {
              phase: "found_sources",
              detail: {
                result_count: 1,
                sources: [{ title: "Trang A", url: "https://a.vn/1", domain: "a.vn" }],
              },
            },
          ],
        })}
      />,
    )

    fireEvent.click(screen.getByText("1 nguồn"))

    expect(screen.getByRole("link", { name: /Trang A/ })).toBeInTheDocument()
    expect(screen.queryByText(/Cập nhật:/)).not.toBeInTheDocument()
  })

  it("closes the trail with what the Turn actually ended as", () => {
    // The blocks of a Turn that hit its deadline look exactly like a whole
    // answer's; this row is the only place the difference shows.
    render(
      <AssistantMessage
        view={view({ searchProgress: [{ phase: "reading_data" }], completed: false })}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /Tiến trình tìm kiếm/ }))

    expect(screen.getByText("Đã dừng")).toBeInTheDocument()
    expect(screen.queryByText("Hoàn thành")).not.toBeInTheDocument()
  })

  it("offers a follow-up without asking it", () => {
    // Pressing one fills the composer; it never spends a Turn the reader has not
    // decided to spend.
    const onAsk = vi.fn()
    render(
      <AssistantMessage
        view={view({ suggestions: ["Chủ tịch Masan hiện tại là ai?"] })}
        showSuggestions
        onAsk={onAsk}
      />,
    )

    fireEvent.click(screen.getByText("Chủ tịch Masan hiện tại là ai?"))

    expect(onAsk).toHaveBeenCalledWith("Chủ tịch Masan hiện tại là ai?")
  })

  it("keeps follow-ups off every answer but the newest", () => {
    render(<AssistantMessage view={view({ suggestions: ["một câu hỏi"] })} onAsk={vi.fn()} />)

    expect(screen.queryByText("một câu hỏi")).not.toBeInTheDocument()
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
    render(
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

    fireEvent.click(screen.getByLabelText(/Nguồn của đoạn này/))
    fireEvent.click(screen.getByText("1 nguồn"))
    fireEvent.click(screen.getByText("Sources & methods"))

    // The whole document, not the render container: the source drawer portals
    // to `body`, and a tool name leaking there is the same leak.
    const markup = document.body.innerHTML
    for (const name of TOOL_NAMES) expect(markup).not.toContain(name)
    expect(markup).not.toContain("call_01")
  })

  it("keeps the unit and the as_of one press from the claim they belong to", () => {
    // ADR-0015's first provenance layer. The chip replaced a card in the reading
    // order, not the reader's access to the figure behind the sentence.
    render(<AssistantMessage view={view({ blocks: [block("kết luận", [citation()])] })} />)

    fireEvent.click(screen.getByLabelText(/Nguồn của đoạn này/))

    expect(screen.getByText("12,4")).toBeInTheDocument()
    expect(screen.getByText("%")).toBeInTheDocument()
    expect(screen.getByText("as of 2026-08-14")).toBeInTheDocument()
    expect(screen.getByText("technical.momentum_273d")).toBeInTheDocument()
  })

  it("names the source on the chip and counts the others", () => {
    render(
      <AssistantMessage
        view={view({
          blocks: [
            block("kết luận", [
              citation({ source: "external_claim", provenance: "www.masangroup.com" }),
              citation({ source: "external_claim", provenance: "e.vnexpress.net" }),
            ]),
          ],
        })}
      />,
    )

    expect(screen.getByText("masangroup +1")).toBeInTheDocument()
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
