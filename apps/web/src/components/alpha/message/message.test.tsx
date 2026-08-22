// @vitest-environment jsdom
/**
 * What an answer puts on screen, and what it must never put there.
 *
 * The surface is prose plus the calls that produced it, so the assertions split
 * the same way: the Markdown is rendered rather than shown with its syntax, no
 * path exists from model output to markup, and a call is one row that changes
 * status rather than two rows that accumulate.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, within } from "@testing-library/react"

import { TOOL_CALL_COPY, terminalSentence } from "@/lib/alpha-desk/copy"
import type { AssistantView, DraftEntry } from "@/lib/alpha-desk/transcript"
import type { ToolCall } from "@/lib/alpha-desk/types"
import { AssistantMessage } from "./assistant-message"
import { DraftMessage } from "./draft-message"

afterEach(cleanup)

function call(overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    id: "call-1",
    name: "web_search",
    status: "running",
    summary: "Đang tìm trên web",
    ...overrides,
  }
}

function view(overrides: Partial<AssistantView> = {}): AssistantView {
  return { text: "một câu trả lời", toolCalls: [], completed: true, ...overrides }
}

function draft(overrides: Partial<DraftEntry> = {}): DraftEntry {
  return {
    kind: "draft",
    key: "draft-1",
    text: "",
    toolCalls: [],
    phase: "running",
    terminalReason: null,
    ...overrides,
  }
}

describe("the answer's prose", () => {
  it("renders the Markdown the model wrote instead of showing its syntax", () => {
    render(<AssistantMessage view={view({ text: "**Nguyễn Đăng Quang** là chủ tịch." })} />)

    expect(screen.getByText("Nguyễn Đăng Quang").tagName).toBe("STRONG")
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument()
  })

  it("renders a GFM table, because a table is what a comparison arrives as", () => {
    render(
      <AssistantMessage
        view={view({ text: "| Mã | Giá |\n| --- | --- |\n| FPT | 100 |" })}
      />,
    )

    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: "Mã" })).toBeInTheDocument()
  })

  it("opens a link in a new tab and sends no referrer with it", () => {
    // The prose can be written out of untrusted external pages, so a link in it
    // is not a link this product vouches for.
    render(<AssistantMessage view={view({ text: "[nguồn](https://example.com/a)" })} />)

    const link = screen.getByRole("link", { name: "nguồn" })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("renders an HTML tag in the answer as the text it is", () => {
    // There is no raw-HTML path in the plugin chain, which is why no sanitiser
    // is needed rather than why one was skipped.
    const { container } = render(
      <AssistantMessage view={view({ text: '<img src=x onerror="alert(1)">' })} />,
    )

    expect(container.querySelector("img")).toBeNull()
    expect(screen.getByText(/onerror/)).toBeInTheDocument()
  })
})

describe("the tool calls behind an answer", () => {
  it("names each call by the summary the backend sent, with its outcome beside it", () => {
    render(
      <AssistantMessage
        view={view({
          toolCalls: [
            call({ id: "a", status: "ok", summary: "Đã tìm trên web" }),
            call({ id: "b", status: "error", summary: "Không mở được trang" }),
          ],
        })}
      />,
    )

    const list = within(screen.getByRole("list", { name: TOOL_CALL_COPY.label }))
    const rows = list.getAllByRole("listitem")
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent("Đã tìm trên web")
    expect(rows[0]).toHaveTextContent(TOOL_CALL_COPY.ok)
    expect(rows[1]).toHaveTextContent(TOOL_CALL_COPY.error)
  })

  it("draws no list at all on an answer that used no tool", () => {
    render(<AssistantMessage view={view()} />)

    expect(screen.queryByRole("list", { name: TOOL_CALL_COPY.label })).not.toBeInTheDocument()
  })

  it("shows a call still running as running, on the draft it belongs to", () => {
    render(<DraftMessage entry={draft({ toolCalls: [call()] })} onRetry={vi.fn()} />)

    expect(screen.getByText(TOOL_CALL_COPY.running)).toBeInTheDocument()
    expect(screen.getByText("Đang tìm trên web")).toBeInTheDocument()
  })
})

describe("an answer that stopped early", () => {
  it("says so under the text rather than in place of it", () => {
    render(<AssistantMessage view={view({ text: "một nửa câu", completed: false })} />)

    expect(screen.getByText("một nửa câu")).toBeInTheDocument()
    expect(screen.getByText(terminalSentence(null))).toBeInTheDocument()
  })

  it("says nothing on an answer that ran to completion", () => {
    render(<AssistantMessage view={view()} />)

    expect(screen.queryByText(terminalSentence(null))).not.toBeInTheDocument()
  })
})

describe("the Turn in flight", () => {
  it("shows that it is working before the first delta and the first call", () => {
    render(<DraftMessage entry={draft()} onRetry={vi.fn()} />)

    expect(screen.getByRole("status")).toHaveTextContent("Đang chuẩn bị…")
  })

  it("drops that line as soon as anything has arrived", () => {
    render(<DraftMessage entry={draft({ text: "câu đầu" })} onRetry={vi.fn()} />)

    expect(screen.queryByText("Đang chuẩn bị…")).not.toBeInTheDocument()
    expect(screen.getByText("câu đầu")).toBeInTheDocument()
  })

  it("keeps what arrived and offers a retry when the Turn ended badly", () => {
    // Never a full-screen error: a Turn that hit its deadline still said
    // something, and replacing it with an error page throws away the only part
    // the reader wanted.
    render(
      <DraftMessage
        entry={draft({ text: "một nửa", phase: "incomplete", terminalReason: "turn_deadline" })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByText("một nửa")).toBeInTheDocument()
    expect(screen.getByText(terminalSentence("turn_deadline"))).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument()
  })

  it("never shows a stable reason code, whatever the code is", () => {
    render(
      <DraftMessage
        entry={draft({ phase: "failed", terminalReason: "a_reason_never_mapped" })}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.queryByText(/a_reason_never_mapped/)).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(terminalSentence(null))
  })

  it("says nothing under a Turn that simply finished", () => {
    render(<DraftMessage entry={draft({ text: "xong", phase: "completed" })} onRetry={vi.fn()} />)

    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
  })

  it("carries no flag control, because a flag names a message this draft has not got", () => {
    render(<DraftMessage entry={draft({ text: "một nửa" })} onRetry={vi.fn()} />)

    expect(screen.queryByRole("button", { name: /báo lỗi/i })).not.toBeInTheDocument()
  })
})
