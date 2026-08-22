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
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import { FLAG_COPY, TOOL_CALL_COPY, terminalSentence } from "@/lib/alpha-desk/copy"
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
    round: 0,
    result_count: 0,
    results: [],
    ...overrides,
  }
}

function view(overrides: Partial<AssistantView> = {}): AssistantView {
  return {
    text: "một câu trả lời",
    toolCalls: [],
    thoughts: [],
    followUps: [],
    elapsedMs: 0,
    completed: true,
    ...overrides,
  }
}

function draft(overrides: Partial<DraftEntry> = {}): DraftEntry {
  return {
    kind: "draft",
    key: "draft-1",
    text: "",
    toolCalls: [],
    thoughts: [],
    elapsedMs: 0,
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
  it("names each call by the summary the backend sent, and marks the one that failed", () => {
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

    // A finished Turn keeps its work folded away; the reader opens it.
    fireEvent.click(screen.getByRole("button", { name: /Đã làm việc trong/ }))

    // Two calls in one round, so the timeline groups them under a count and
    // lists each by the sentence the backend wrote — never one it composed.
    expect(screen.getByText("Đã chạy 2 truy vấn")).toBeInTheDocument()
    expect(screen.getByText("Đã tìm trên web")).toBeInTheDocument()
    expect(screen.getByText("Không mở được trang")).toBeInTheDocument()
    // A call that failed must not read as a call that found nothing.
    expect(screen.getByText(TOOL_CALL_COPY.error)).toBeInTheDocument()
  })

  it("draws no timeline at all on an answer that used no tool and said nothing on the way", () => {
    render(<AssistantMessage view={view()} />)

    expect(screen.queryByText(/Đã làm việc trong/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Đã chạy/)).not.toBeInTheDocument()
  })

  it("shows the work open while the Turn is still running", () => {
    render(<DraftMessage entry={draft({ toolCalls: [call()] })} onRetry={vi.fn()} />)

    // Open by default while running, because the point of it is to show the
    // reader that something is happening rather than to be discoverable.
    expect(screen.getByText("Đang làm việc…")).toBeInTheDocument()
    expect(screen.getByText("Đang tìm trên web")).toBeInTheDocument()
  })

  it("keeps the narration out of the answer and in the timeline", () => {
    render(
      <AssistantMessage
        view={view({
          text: "Câu trả lời.",
          thoughts: [{ round: 0, text: "Đang tra tin hôm nay" }],
          toolCalls: [call({ id: "a", status: "ok", summary: "Đã tìm trên web" })],
        })}
      />,
    )

    // The answer is readable without opening anything; the narration is not
    // part of it and lives behind the toggle.
    expect(screen.getByText("Câu trả lời.")).toBeInTheDocument()

    // Folded away rather than absent: the rows stay mounted so the fold can
    // animate, so what says "collapsed" is the disclosure state.
    const toggle = screen.getByRole("button", { name: /Đã làm việc trong/ })
    expect(toggle).toHaveAttribute("aria-expanded", "false")

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByText("Đang tra tin hôm nay")).toBeInTheDocument()
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

describe("the positive verdict", () => {
  it("offers no thumb at all on a surface with nowhere to record it", () => {
    render(<AssistantMessage view={view()} messageId={7} />)

    // A control that lights up and forgets is worse than a control that is not
    // offered, so the button is conditional on the handler and not on the
    // message.
    expect(
      screen.queryByRole("button", { name: "Hữu ích" }),
    ).not.toBeInTheDocument()
  })

  it("marks the answer and takes the mark back through the same control", () => {
    const onHelpful = vi.fn()
    const { rerender } = render(
      <AssistantMessage view={view()} messageId={7} onHelpful={onHelpful} />,
    )

    const thumb = screen.getByRole("button", { name: "Hữu ích" })
    expect(thumb).toHaveAttribute("aria-pressed", "false")
    fireEvent.click(thumb)
    expect(onHelpful).toHaveBeenCalledWith(7, true)

    // The pressed state comes from the caller, so a mark that was recorded
    // survives a re-render instead of resetting.
    rerender(
      <AssistantMessage
        view={view()}
        messageId={7}
        helpful
        onHelpful={onHelpful}
      />,
    )
    const marked = screen.getByRole("button", { name: "Hữu ích" })
    expect(marked).toHaveAttribute("aria-pressed", "true")
    fireEvent.click(marked)
    expect(onHelpful).toHaveBeenLastCalledWith(7, false)
  })

  it("puts away the dispute control the down-vote opened, because it is the other answer", () => {
    render(
      <AssistantMessage
        view={view()}
        messageId={7}
        onHelpful={vi.fn()}
        onFlag={vi.fn()}
        onUnflag={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Chưa đúng" }))
    expect(
      screen.getByRole("button", { name: FLAG_COPY.action }),
    ).toBeInTheDocument()

    // The two verdicts are one question with two answers on this surface: the
    // reader who changes their mind should not be left with the dispute half
    // still open under a message they just approved.
    fireEvent.click(screen.getByRole("button", { name: "Hữu ích" }))
    expect(
      screen.queryByRole("button", { name: FLAG_COPY.action }),
    ).not.toBeInTheDocument()
  })
})
