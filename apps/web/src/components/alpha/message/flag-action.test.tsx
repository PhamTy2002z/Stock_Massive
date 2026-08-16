// @vitest-environment jsdom
/**
 * What flagging a message does, and — the part that matters — what it does not.
 *
 * V1 has no dispute workflow (`docs/adr/0016`). Every claim below is one a
 * conventional feedback widget gets wrong by being reassuring: it thanks the
 * user, hands them a reference number, tells them somebody will look into it,
 * and offers a comment box nobody reads. Each of those is a promise this system
 * has no mechanism to keep, so each is asserted absent.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"

import { FLAG_REASON_LABELS } from "@/lib/alpha-desk/copy"
import type { AssistantView } from "@/lib/alpha-desk/transcript"
import type { ContentBlock, RiskNotice } from "@/lib/alpha-desk/types"
import { AssistantMessage } from "./assistant-message"
import { FlagAction } from "./flag-action"

afterEach(cleanup)

const NOTICE: RiskNotice = {
  version: "risk-notice/1",
  locale: "vi",
  text: "Đây không phải khuyến nghị đầu tư.",
  meanings: [],
}

function block(text: string): ContentBlock {
  return { kind: "prose", text, symbol: null, trading_day: null, citations: [] }
}

function view(): AssistantView {
  return { blocks: [block("kết luận")], riskNotice: NOTICE, sourcesAndMethods: [] }
}

function action(overrides: Partial<React.ComponentProps<typeof FlagAction>> = {}) {
  const props = {
    messageId: 7,
    reason: null,
    onFlag: vi.fn(),
    onUnflag: vi.fn(),
    ...overrides,
  }
  render(<FlagAction {...props} />)
  return props
}

function open() {
  fireEvent.click(screen.getByRole("button", { name: /báo lỗi/i }))
  return screen.getByRole("menu")
}

describe("the four reasons", () => {
  it("offers exactly the four the backend can store, and no fifth", () => {
    action()
    const menu = within(open())

    for (const label of Object.values(FLAG_REASON_LABELS)) {
      expect(menu.getByRole("menuitemradio", { name: label })).toBeInTheDocument()
    }
    expect(menu.getAllByRole("menuitemradio")).toHaveLength(4)
  })

  it("names them in the reader's language and never by the stored code", () => {
    action()
    const menu = open()

    // `wrong_figure` is a column value. A reader flags an answer because the
    // number is wrong, not because a label is.
    expect(menu.textContent).not.toMatch(/wrong_figure|overreach|wrongly_refused/)
    expect(menu.textContent).toMatch(/Số liệu sai/)
  })

  it("offers no free-text field, because nothing reads one", () => {
    action()
    open()

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  })

  it("carries the message id with the reason", () => {
    const props = action({ messageId: 42 })
    const menu = within(open())

    fireEvent.click(menu.getByRole("menuitemradio", { name: /Số liệu sai/ }))

    expect(props.onFlag).toHaveBeenCalledWith(42, "wrong_figure")
  })
})

describe("once a message is flagged", () => {
  it("acknowledges it and promises nothing", () => {
    render(<FlagAction messageId={7} reason="overreach" onFlag={vi.fn()} onUnflag={vi.fn()} />)

    const acknowledgement = screen.getByText(/Đã ghi nhận/)
    expect(acknowledgement).toBeInTheDocument()
    // No ticket, no reply, no deadline, and nobody getting back to them.
    expect(acknowledgement.textContent).not.toMatch(
      /sẽ liên hệ|phản hồi trong|mã yêu cầu|ticket|xử lý trong/i,
    )
    // A reference number is the single most common way a surface implies a
    // process. There is no process, so there is no number.
    expect(acknowledgement.textContent).not.toMatch(/#\d|\bmã số\b/i)
  })

  it("shows which reason is on the message", () => {
    render(<FlagAction messageId={7} reason="overreach" onFlag={vi.fn()} onUnflag={vi.fn()} />)

    expect(screen.getByText(FLAG_REASON_LABELS.overreach)).toBeInTheDocument()
    const menu = within(open())
    expect(
      menu.getByRole("menuitemradio", { name: FLAG_REASON_LABELS.overreach }),
    ).toHaveAttribute("aria-checked", "true")
  })

  it("replaces the reason rather than adding a second one", () => {
    const props = action({ reason: "overreach" })
    const menu = within(open())

    fireEvent.click(menu.getByRole("menuitemradio", { name: FLAG_REASON_LABELS.other }))

    // One call, carrying the new reason. The pair on the row is overwritten;
    // nothing accumulates, because there is no table for it to accumulate in.
    expect(props.onFlag).toHaveBeenCalledOnce()
    expect(props.onFlag).toHaveBeenCalledWith(7, "other")
  })

  it("can be cleared again", () => {
    const props = action({ reason: "other" })
    const menu = within(open())

    fireEvent.click(menu.getByRole("menuitem", { name: /Bỏ đánh dấu/ }))

    expect(props.onUnflag).toHaveBeenCalledWith(7)
  })

  it("offers nothing to clear while the message carries no flag", () => {
    action()
    const menu = within(open())

    expect(menu.queryByRole("menuitem", { name: /Bỏ đánh dấu/ })).not.toBeInTheDocument()
  })
})

describe("when the write is rejected", () => {
  it("says so, rather than leaving the press unanswered", () => {
    // The counterpart to the acknowledgement. Silence after a press reads as
    // "recorded", which is the one thing a rejected write must not say.
    render(
      <FlagAction
        messageId={7}
        reason={null}
        failed
        onFlag={vi.fn()}
        onUnflag={vi.fn()}
      />,
    )

    expect(screen.getByRole("alert")).toHaveTextContent(/Chưa ghi được đánh dấu/)
  })

  it("does not also claim the flag was recorded", () => {
    // A failed write against a message that still carries an older flag must
    // not show both sentences at once — one of them would be false.
    render(
      <FlagAction
        messageId={7}
        reason="overreach"
        failed
        onFlag={vi.fn()}
        onUnflag={vi.fn()}
      />,
    )

    expect(screen.queryByText(/Đã ghi nhận/)).not.toBeInTheDocument()
  })

  it("still offers the reasons, because pressing again is the whole retry", () => {
    action({ failed: true })
    const menu = within(open())

    expect(menu.getAllByRole("menuitemradio")).toHaveLength(4)
  })
})

describe("the control itself", () => {
  it("stays out of the way until it is opened", () => {
    action()

    // Unobtrusive means unobtrusive: no reasons on screen, and no "was this
    // helpful?" bar under every answer.
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(screen.queryByText(FLAG_REASON_LABELS.wrong_figure)).not.toBeInTheDocument()
  })

  it("is reachable by name, not only by its icon", () => {
    action()

    expect(screen.getByRole("button", { name: /báo lỗi câu trả lời/i })).toBeInTheDocument()
  })
})

describe("where the action lives", () => {
  it("sits on a canonical assistant message", () => {
    render(
      <AssistantMessage
        view={view()}
        messageId={3}
        flaggedReason={null}
        onFlag={vi.fn()}
        onUnflag={vi.fn()}
      />,
    )

    expect(screen.getByRole("button", { name: /báo lỗi/i })).toBeInTheDocument()
  })

  it("is absent where there is nowhere to send it", () => {
    // A surface with no handler renders no control, rather than one that
    // swallows the press and leaves the reader thinking they objected.
    render(<AssistantMessage view={view()} messageId={3} />)

    expect(screen.queryByRole("button", { name: /báo lỗi/i })).not.toBeInTheDocument()
  })
})
