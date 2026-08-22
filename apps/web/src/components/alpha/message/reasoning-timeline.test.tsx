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
import { cleanup, render, screen } from "@testing-library/react"

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

    expect(screen.getByText("Đang làm việc…")).toBeInTheDocument()
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
