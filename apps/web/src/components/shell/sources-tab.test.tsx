// @vitest-environment jsdom
/**
 * How the sources panel draws the two kinds of evidence apart.
 *
 * A local-memory Turn once put many rows on this panel, every one with a globe
 * icon and a `0` beside it. Three separate
 * lies in one row: the raw tool name told the reader nothing, the globe said a
 * result out of our own Postgres came off the open web, and the `0` beside a
 * call that had succeeded read as "found nothing".
 *
 * The backend fixed the sentence. What is tested here is the rest of it:
 *
 * *A count belongs only where results are what came back.* A search has pages
 * and their number is the reader's first question. A store read answers with one
 * local result and no sources.
 *
 * *A dozen reads of the same kind are one row.* They differ only in which figure
 * query was named, so a dozen rows is a panel scrolled past rather than read — but the
 * names are still there one click away, because the reader opened this to check.
 *
 * *A search is never folded in with them.* Each one has its own pages behind it,
 * and those pages are the thing this panel exists for.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { ToolCall } from "@/lib/alpha-desk/types"

const MESSAGE_ID = 7

// Mocked at the hook boundary, the way the other shell suites do it: what is
// under test is how this panel draws a transcript, not how the shell assembles
// one.
const desk = { entries: [] as unknown[] }

vi.mock("./desk-state", () => ({ useDesk: () => desk }))
vi.mock("./shell-state", () => ({
  useShell: () => ({
    state: { inspector: "sources", sourcesMessageId: MESSAGE_ID },
    dispatch: () => {},
  }),
}))

vi.mock("@/components/alpha/message/source-list", () => ({
  SourceList: () => null,
}))

import { SourcesTab } from "./sources-tab"

afterEach(cleanup)

function call(overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    id: "call-1",
    name: "web_search",
    status: "ok",
    summary: "Tìm trên web: SSI quý 2",
    round: 0,
    error: null,
    result_count: 5,
    results: [],
    kind: "external",
    ...overrides,
  }
}

function storeCall(index: number, summary: string): ToolCall {
  return call({
    id: `store-${index}`,
    name: "session_search",
    summary,
    result_count: 0,
    kind: "store",
  })
}

/** One answer in the transcript, and this panel rendered over it. */
function show(toolCalls: ToolCall[]) {
  desk.entries = [
    { kind: "assistant", messageId: MESSAGE_ID, view: { thoughts: [], toolCalls } },
  ]
  return render(<SourcesTab />)
}

describe("the count beside a row", () => {
  it("is shown for a search, where the number of pages is the question", () => {
    show([call({ result_count: 5 })])

    expect(screen.getByText("5")).toBeInTheDocument()
  })

  it("is not shown for a store read, which has no results to count", () => {
    show([storeCall(1, "Tìm trong hội thoại trước: SSI")])

    // The bug this replaces: a `0` beside a call that succeeded.
    expect(screen.queryByText("0")).not.toBeInTheDocument()
  })
})

describe("a run of store reads", () => {
  const reads = [
    storeCall(1, "Tìm trong hội thoại trước: SSI"),
    storeCall(2, "Đọc lại ghi chú: SSI"),
    storeCall(3, "Ghi nhớ: khẩu vị rủi ro"),
  ]

  it("collapses to one row saying how many", () => {
    show(reads)

    expect(screen.getByText("Đã chạy 3 công cụ nội bộ")).toBeInTheDocument()
    expect(screen.queryByText("Tìm trong hội thoại trước: SSI")).not.toBeInTheDocument()
  })

  it("lists every figure it read once it is opened", () => {
    show(reads)

    fireEvent.click(screen.getByRole("button", { expanded: false }))

    for (const read of reads) {
      expect(screen.getByText(read.summary)).toBeInTheDocument()
    }
  })

  it("stays a plain row when there was only one read", () => {
    show([storeCall(1, "Tìm trong hội thoại trước: SSI")])

    expect(screen.getByText("Tìm trong hội thoại trước: SSI")).toBeInTheDocument()
    expect(screen.queryByText(/công cụ nội bộ/)).not.toBeInTheDocument()
  })

  it("never swallows a search that happened beside it", () => {
    show([...reads, call({ id: "web-1", summary: "Tìm trên web: SSI quý 2" })])

    expect(screen.getByText("Đã chạy 3 công cụ nội bộ")).toBeInTheDocument()
    expect(screen.getByText("Tìm trên web: SSI quý 2")).toBeInTheDocument()
  })

  it("keeps the order the model asked in, rather than sorting by kind", () => {
    /* A round that read, searched, then read again is three stretches. Folding
       it into "all reads then all searches" would describe work that did not
       happen. */
    show([
      storeCall(1, "Tìm trong hội thoại trước: SSI"),
      storeCall(2, "Đọc lại ghi chú: SSI"),
      call({ id: "web-1", summary: "Tìm trên web: SSI quý 2" }),
      storeCall(3, "Ghi nhớ: SSI"),
    ])

    expect(screen.getByText("Đã chạy 2 công cụ nội bộ")).toBeInTheDocument()
    // The single read after the search is its own row, not folded backwards.
    expect(
      screen.getByText("Ghi nhớ: SSI"),
    ).toBeInTheDocument()
  })
})

describe("a call whose provenance was never stated", () => {
  it("reads as outside content, which is the safe direction", () => {
    const withoutKind: ToolCall = call({ result_count: 3 })
    delete withoutKind.kind
    show([withoutKind])

    // Drawn as a search: it gets its count back.
    expect(screen.getByText("3")).toBeInTheDocument()
  })
})
