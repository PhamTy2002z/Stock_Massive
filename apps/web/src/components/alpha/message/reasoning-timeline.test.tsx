// @vitest-environment jsdom
/**
 * What the timeline groups, in what order, and when it is worth opening.
 *
 * A round is the fact the backend already knows and the client must not
 * re-derive from timing, so the grouping assertions key everything off
 * `round` rather than off array position. The open/closed assertions are
 * the other half of the contract: a reader watching a Turn run should not
 * have to click anything to see it, and a reader who scrolled back to a
 * finished one should not have to close anything to read the answer under it.
 */

import { afterEach, describe, expect, it } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { Thought, ToolCall, ToolResult } from "@/lib/alpha-desk/types"
import { ReasoningTimeline } from "./reasoning-timeline"
import { SourceList } from "./source-list"

afterEach(cleanup)

function call(overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    id: "call-1",
    name: "web_search",
    status: "ok",
    summary: "Đã tra dữ liệu cho STB giá 12 tháng",
    round: 0,
    error: null,
    result_count: 0,
    results: [],
    ...overrides,
  }
}

function thought(overrides: Partial<Thought> = {}): Thought {
  return { round: 0, text: "Đang xem xét dữ liệu giá", ...overrides }
}

function result(overrides: Partial<ToolResult> = {}): ToolResult {
  return {
    title: "Một bài viết",
    url: "https://example.com/a",
    source: "example.com",
    snippet: "Một đoạn trích",
    ...overrides,
  }
}

describe("grouping tool calls by round", () => {
  it("collapses a round with two or more calls into one count row", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[
          call({ id: "a", round: 0, summary: "Đã tra dữ liệu cho BCTC Q2/2026" }),
          call({ id: "b", round: 0, summary: "Đã tra dữ liệu cho đấu giá VAMC" }),
        ]}
        elapsedMs={5000}
        running
      />,
    )

    expect(screen.getByText("Đã chạy 2 truy vấn")).toBeInTheDocument()
    expect(screen.getByText("Đã tra dữ liệu cho BCTC Q2/2026")).toBeInTheDocument()
    expect(screen.getByText("Đã tra dữ liệu cho đấu giá VAMC")).toBeInTheDocument()
  })

  it("keeps a round with exactly one call as its own row, uncollapsed", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ round: 0, summary: "Đã tra dữ liệu cho STB giá 12 tháng" })]}
        elapsedMs={5000}
        running
      />,
    )

    expect(screen.queryByText(/Đã chạy \d+ truy vấn/)).not.toBeInTheDocument()
    expect(screen.getByText("Đã tra dữ liệu cho STB giá 12 tháng")).toBeInTheDocument()
  })

  it("shows the result count and no expandable card on a call with no results", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ round: 0, result_count: 6, results: [] })]}
        elapsedMs={5000}
        running
      />,
    )

    expect(screen.getByText("6 kết quả")).toBeInTheDocument()
  })
})

describe("the order rounds render in", () => {
  it("puts a round's thought before its calls, and rounds ascending", () => {
    render(
      <ReasoningTimeline
        thoughts={[thought({ round: 1, text: "Đối chiếu chuỗi giá với thanh khoản" })]}
        toolCalls={[
          call({ id: "later", round: 1, summary: "Đã chạy sau" }),
          call({ id: "earlier", round: 0, summary: "Đã chạy trước" }),
        ]}
        elapsedMs={5000}
        running
      />,
    )

    // DOM order is reading order: round 0's call before round 1's thought
    // before round 1's call — a straight "A before B before C" check.
    const [earlier, mid, later] = [
      "Đã chạy trước",
      "Đối chiếu chuỗi giá với thanh khoản",
      "Đã chạy sau",
    ].map((text) => screen.getByText(text))

    expect(earlier.compareDocumentPosition(mid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(mid.compareDocumentPosition(later) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe("what a failed call is called", () => {
  /**
   * The distinction the reader acts on. A ceiling of ours refusing a call and a
   * page that would not load both end `error`, and they ask opposite things:
   * one is worth trying again, the other is the product saying it has looked
   * enough. Drawing both as "Lỗi" sent readers back to a search engine that was
   * working the whole time.
   */
  it("names the ceiling when the Turn spent its allowance of lookups", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ status: "error", error: "external_budget_exhausted" })]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByText("Hết lượt tra")).toBeInTheDocument()
    expect(screen.queryByText("Lỗi")).not.toBeInTheDocument()
  })

  it("names it inside a grouped round too, where the refusals actually arrive", () => {
    // The shape that produced the complaint: a round fans out, the allowance is
    // already gone, and every call in the group is refused at once.
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[
          call({ id: "a", status: "error", error: "external_budget_exhausted" }),
          call({ id: "b", status: "error", error: "external_budget_exhausted" }),
        ]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getAllByText("Hết lượt tra")).toHaveLength(2)
    expect(screen.queryByText("Lỗi")).not.toBeInTheDocument()
  })

  it("still says Lỗi for a call that really did fail", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ status: "error", error: "tool_failed" })]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByText("Lỗi")).toBeInTheDocument()
  })

  it("falls back to Lỗi for a reason this build has not learned", () => {
    // A backend that grows a new code must not put the code itself on screen.
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ status: "error", error: "some_future_reason" })]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByText("Lỗi")).toBeInTheDocument()
    expect(screen.queryByText("some_future_reason")).not.toBeInTheDocument()
  })
})

describe("saying the Turn has not stopped", () => {
  it("ends in a live row, so the rail is never still while the Turn runs", () => {
    // The stretch that has no other sign of life: every call has returned and
    // the model is deciding what to do next, or writing the answer.
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ status: "ok", summary: "Đã tra dữ liệu cho STB" })]}
        elapsedMs={21000}
        running
      />,
    )

    expect(screen.getByRole("status")).toHaveTextContent("Đang xử lý…")
  })

  it("says it is preparing while there is nothing to show yet", () => {
    render(<ReasoningTimeline thoughts={[]} toolCalls={[]} elapsedMs={0} running />)

    expect(screen.getByRole("status")).toHaveTextContent("Đang chuẩn bị…")
  })

  it("counts the seconds on the line that survives the fold being shut", () => {
    render(<ReasoningTimeline thoughts={[]} toolCalls={[]} elapsedMs={21400} running />)

    expect(screen.getByRole("button", { name: /Đang làm việc · 21s/ })).toBeInTheDocument()
  })

  it("prints no figure before there is a second of it", () => {
    render(<ReasoningTimeline thoughts={[]} toolCalls={[]} elapsedMs={300} running />)

    expect(screen.getByText("Đang làm việc…")).toBeInTheDocument()
  })

  it("takes the live row away the moment the Turn is over", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ summary: "Đã tra dữ liệu cho STB" })]}
        elapsedMs={12000}
        running={false}
      />,
    )

    expect(screen.queryByRole("status")).not.toBeInTheDocument()
  })
})

describe("opening and closing by default", () => {
  it("opens on its own while the Turn is still running", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ summary: "Đã tra dữ liệu cho STB" })]}
        elapsedMs={3000}
        running
      />,
    )

    expect(screen.getByText("Đang làm việc · 3s")).toBeInTheDocument()
    expect(screen.getByText("Đã tra dữ liệu cho STB")).toBeInTheDocument()
  })

  it("collapses on its own once the Turn has finished", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ summary: "Đã tra dữ liệu cho STB" })]}
        elapsedMs={12000}
        running={false}
      />,
    )

    expect(screen.getByText("Đã làm việc trong 12s")).toBeInTheDocument()
    // The rows stay mounted so the fold can animate them away, so "collapsed"
    // is a statement about the disclosure and not about the DOM.
    expect(screen.getByRole("button", { name: /Đã làm việc trong 12s/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    )
    expect(screen.getByText("Đã tra dữ liệu cho STB").closest("[aria-hidden]")).toHaveAttribute(
      "aria-hidden",
      "true",
    )
  })

  it("renders nothing at all for a Turn that neither thought nor called, and is not running", () => {
    const { container } = render(
      <ReasoningTimeline thoughts={[]} toolCalls={[]} elapsedMs={0} running={false} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})

describe("a source result's text", () => {
  it("renders the snippet as text rather than as Markdown or HTML", () => {
    render(<SourceList results={[result({ snippet: "**không** phải markdown" })]} />)

    expect(screen.getByText("**không** phải markdown")).toBeInTheDocument()
    expect(screen.queryByRole("strong")).not.toBeInTheDocument()
  })

  it("drops the link when the url is not http or https, but keeps the title on screen", () => {
    render(
      <SourceList
        results={[
          result({ title: "Đường dẫn không an toàn", url: "javascript:alert(1)" }),
        ]}
      />,
    )

    expect(screen.getByText("Đường dẫn không an toàn")).toBeInTheDocument()
    expect(screen.queryByRole("link")).not.toBeInTheDocument()
  })

  it("keeps the link, opened safely, for an ordinary http(s) result", () => {
    render(<SourceList results={[result({ title: "Đường dẫn an toàn" })]} />)

    const link = screen.getByRole("link", { name: /Đường dẫn an toàn/ })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow")
  })
})


describe("a round of store reads", () => {
  /**
   * A Turn analysing HPG read twelve figures in one breath. The rail called them
   * "truy vấn" — a word for a query against something outside — and gave each of
   * the twelve its own icon, which made a dozen subordinate rows read as a dozen
   * peers of the line naming them.
   */
  const reads = [
    call({ id: "a", kind: "store", summary: "Tìm trong hội thoại trước: HPG" }),
    call({ id: "b", kind: "store", summary: "Đọc lại ghi chú: HPG" }),
    call({ id: "c", kind: "store", summary: "Ghi nhớ: HPG" }),
  ]

  it("is counted in the words for the work it actually did", () => {
    render(
      <ReasoningTimeline thoughts={[]} toolCalls={reads} elapsedMs={5000} running />,
    )

    expect(screen.getByText("Đã chạy 3 công cụ nội bộ")).toBeInTheDocument()
    expect(screen.queryByText(/truy vấn/)).not.toBeInTheDocument()
  })

  it("still names every figure it read", () => {
    render(
      <ReasoningTimeline thoughts={[]} toolCalls={reads} elapsedMs={5000} running />,
    )

    for (const read of reads) {
      expect(screen.getByText(read.summary)).toBeInTheDocument()
    }
  })

  it("keeps the query wording for a round of searches", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ id: "a" }), call({ id: "b" })]}
        elapsedMs={5000}
        running
      />,
    )

    expect(screen.getByText("Đã chạy 2 truy vấn")).toBeInTheDocument()
  })

  /**
   * A Turn analysing a portfolio reads the same four figures for seven symbols,
   * and twenty-eight near-identical lines are longer than the answer they were
   * gathered for. The count is what the reader needs at that size; the lines are
   * what they can ask for.
   */
  describe("at portfolio size", () => {
    const portfolio = (status: ToolCall["status"] = "ok") =>
      ["VCB", "BID", "CTG", "MBB", "TCB", "ACB", "VPB"].flatMap((symbol) =>
        ["Phân vị động lượng", "Phân vị ROE"].map((field) =>
          call({
            id: `${symbol}-${field}`,
            kind: "store",
            status,
            summary: `Tìm trong hội thoại trước: ${field} — ${symbol}`,
          }),
        ),
      )

    it("arrives folded, with the count standing in for the lines", () => {
      const calls = portfolio()
      render(
        <ReasoningTimeline thoughts={[]} toolCalls={calls} elapsedMs={5000} running />,
      )

      expect(screen.getByText("Đã chạy 14 công cụ nội bộ")).toBeInTheDocument()
      expect(screen.queryByText(calls[0].summary)).not.toBeInTheDocument()
    })

    it("opens on a press, and names every figure it read", () => {
      const calls = portfolio()
      render(
        <ReasoningTimeline thoughts={[]} toolCalls={calls} elapsedMs={5000} running />,
      )

      fireEvent.click(screen.getByRole("button", { name: /Đã chạy 14 công cụ nội bộ/ }))

      for (const read of calls) {
        expect(screen.getByText(read.summary)).toBeInTheDocument()
      }
    })

    it("says how many are back while the rows that would say it are folded", () => {
      const calls = [...portfolio(), call({ id: "late", kind: "store", status: "running" })]
      render(
        <ReasoningTimeline thoughts={[]} toolCalls={calls} elapsedMs={5000} running />,
      )

      expect(screen.getByText("· 14/15")).toBeInTheDocument()
    })

    it("says how many failed, which folding them away would have hidden", () => {
      const calls = [
        ...portfolio(),
        call({ id: "bad", kind: "store", status: "error", error: "tool_error" }),
      ]
      render(
        <ReasoningTimeline thoughts={[]} toolCalls={calls} elapsedMs={5000} running />,
      )

      expect(screen.getByText("· 1 lỗi")).toBeInTheDocument()
    })
  })

  it("falls back to the query wording when the round mixed both kinds", () => {
    /* No single kind to state in the header, so the header does not claim one. */
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ id: "a", kind: "store" }), call({ id: "b" })]}
        elapsedMs={5000}
        running
      />,
    )

    expect(screen.getByText("Đã chạy 2 truy vấn")).toBeInTheDocument()
  })
})

/**
 * A rail that says what each lookup asked and nothing about what it found tells
 * a reader the Turn was busy, not whether the answer rests on anything. The
 * facts were already on the wire — `results[].source` and `result_count` — and
 * had simply never been drawn on the rows where the parallel searches land.
 */
describe("how many publishers a lookup came back with", () => {
  const twoDomains = [
    result({ url: "https://cafef.vn/a", source: "cafef.vn" }),
    result({ url: "https://cafef.vn/b", source: "cafef.vn" }),
    result({ url: "https://vnexpress.net/c", source: "vnexpress.net" }),
  ]

  it("counts distinct publishers rather than results", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ result_count: 3, results: twoDomains })]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByText("2 nguồn")).toBeInTheDocument()
    expect(screen.queryByText("3 nguồn")).not.toBeInTheDocument()
  })

  it("draws it on the branch rows of a round, where parallel searches land", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[
          call({ id: "a", result_count: 3, results: twoDomains }),
          call({
            id: "b",
            result_count: 1,
            results: [result({ url: "https://tuoitre.vn/d", source: "tuoitre.vn" })],
          }),
        ]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByText("Đã chạy 2 truy vấn")).toBeInTheDocument()
    expect(screen.getByText("2 nguồn")).toBeInTheDocument()
    expect(screen.getByText("1 nguồn")).toBeInTheDocument()
  })

  it("names the publishers in text, because three marks are a glance", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[call({ result_count: 3, results: twoDomains })]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByTitle("cafef.vn, vnexpress.net")).toBeInTheDocument()
  })

  it("still draws one row per call", () => {
    const { container } = render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[
          call({ id: "a", result_count: 3, results: twoDomains }),
          call({ id: "b", result_count: 3, results: twoDomains }),
        ]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(container.querySelectorAll("[title='cafef.vn, vnexpress.net']")).toHaveLength(2)
  })

  it("says nothing at all for a store read, which has no publisher", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[
          call({
            name: "session_search",
            kind: "store",
            summary: "Tìm trong hội thoại trước",
            result_count: 1,
            results: [],
          }),
        ]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.queryByText(/nguồn/)).not.toBeInTheDocument()
  })

  it("prints a publisher's name as text and never as markup", () => {
    render(
      <ReasoningTimeline
        thoughts={[]}
        toolCalls={[
          call({
            result_count: 1,
            results: [
              result({ source: "<img src=x onerror=alert(1)>", url: "https://x.vn/a" }),
            ],
          }),
        ]}
        elapsedMs={5000}
        running={false}
      />,
    )

    expect(screen.getByTitle("<img src=x onerror=alert(1)>")).toBeInTheDocument()
    expect(document.querySelector("img[onerror]")).toBeNull()
  })
})

it("keeps the old sentence for a call that counted results but carried none", () => {
  render(
    <ReasoningTimeline
      thoughts={[]}
      toolCalls={[call({ result_count: 6, results: [] })]}
      elapsedMs={5000}
      running={false}
    />,
  )

  expect(screen.getByText("6 kết quả")).toBeInTheDocument()
})
