// @vitest-environment jsdom
/**
 * What the shell promises about the three regions it arranges.
 *
 * The rules worth testing here are the ones that couple regions to each other,
 * because those are exactly the ones a component tree gets wrong: opening the
 * inspector on a narrow screen has to fold the sidebar rather than crush the
 * conversation, one overlay at a time may float, and a question offered by a
 * panel has to arrive in the composer *unsent*.
 *
 * The conversation itself is mocked at the context boundary. This file is about
 * the box, not about the Turn — the Turn's own reducer and the transport are
 * tested where they live.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"

const desk = {
  threadId: null as string | null,
  entries: [] as unknown[],
  canCancel: false,
  isCancelling: false,
  isSubmitting: false,
  refusal: null as string | null,
  flagFailedFor: null as number | null,
  submit: vi.fn(),
  cancel: vi.fn(),
  retry: vi.fn(),
  resend: vi.fn(),
  flag: vi.fn(),
  unflag: vi.fn(),
  dismissRefusal: vi.fn(),
  openThread: vi.fn(),
  newThread: vi.fn(),
  openAnalysis: vi.fn(),
}

vi.mock("./desk-state", () => ({
  useDesk: () => desk,
  DeskProvider: ({ children }: { children: React.ReactNode }) => children,
}))

import { Composer } from "./composer"
import { ChatView } from "./view-chat"
import {
  inspectorWidth,
  maxInspectorWidth,
  ShellProvider,
  useShell,
  type ShellView,
} from "./shell-state"

afterEach(cleanup)

beforeEach(() => {
  desk.entries = []
  desk.canCancel = false
  desk.isCancelling = false
  desk.isSubmitting = false
  desk.refusal = null
  desk.submit.mockClear()
  desk.cancel.mockClear()
  desk.resend.mockClear()
})

/** A window the reducer can decide against. jsdom defaults to 1024 × 768. */
function setViewport(width: number) {
  Object.defineProperty(window, "innerWidth", { value: width, configurable: true })
}

/**
 * The shell's own state, exposed to the test through the same hook every
 * component uses. Asserting through the public hook rather than on the reducer
 * keeps these tests honest about what a component can actually see.
 */
let shell: ReturnType<typeof useShell>

function Probe() {
  shell = useShell()
  return null
}

function mount(children?: React.ReactNode) {
  return render(
    <ShellProvider>
      <Probe />
      {children}
    </ShellProvider>,
  )
}

describe("the inspector against the sidebar", () => {
  it("folds the sidebar rather than crushing the conversation", () => {
    // 1024 − 408 (inspector) − 274 (sidebar) leaves 342px of conversation, well
    // under the 520 the column needs to still be one.
    setViewport(1024)
    mount()

    expect(shell.state.sidebarOpen).toBe(true)

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))

    expect(shell.state.inspector).toBe("market")
    expect(shell.state.sidebarOpen).toBe(false)
  })

  it("leaves the sidebar alone when all three columns fit", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))

    expect(shell.state.sidebarOpen).toBe(true)
  })

  it("clamps a drag to a width that leaves the conversation room", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))
    act(() => shell.dispatch({ type: "resize-inspector", width: 99_999 }))

    expect(inspectorWidth(shell.state)).toBe(maxInspectorWidth(1600))
    expect(inspectorWidth(shell.state)).toBeLessThan(1600 - 420 + 1)
  })

  it("refuses to drag narrower than the panel's own minimum", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))
    act(() => shell.dispatch({ type: "resize-inspector", width: 10 }))

    expect(inspectorWidth(shell.state)).toBe(320)
  })

  it("forgets a dragged width when the panel closes", () => {
    // A panel reopened at yesterday's drag width would be a setting nobody
    // asked to keep.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))
    act(() => shell.dispatch({ type: "resize-inspector", width: 700 }))
    act(() => shell.dispatch({ type: "close-inspector" }))
    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))

    expect(inspectorWidth(shell.state)).toBe(408)
  })

  it("is worth nothing at all while it is closed", () => {
    setViewport(1600)
    mount()

    expect(inspectorWidth(shell.state)).toBe(0)
  })
})

describe("what floats above the surface", () => {
  it("allows exactly one overlay at a time", () => {
    mount()

    act(() => shell.dispatch({ type: "overlay", overlay: "account" }))
    act(() => shell.dispatch({ type: "overlay", overlay: "share" }))

    expect(shell.state.overlay).toBe("share")
  })

  it("closes on Escape, from anywhere", () => {
    mount()

    act(() => shell.dispatch({ type: "overlay", overlay: "palette" }))
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))
    })

    expect(shell.state.overlay).toBeNull()
  })

  it("opens the palette on the platform shortcut", () => {
    mount()

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))
    })

    expect(shell.state.overlay).toBe("palette")
  })

  it("drops whatever floated when the view changes", () => {
    mount()

    act(() => shell.dispatch({ type: "overlay", overlay: "thread" }))
    act(() => shell.dispatch({ type: "view", view: "board" as ShellView }))

    expect(shell.state.overlay).toBeNull()
    expect(shell.state.view).toBe("board")
  })
})

describe("a question offered by a panel", () => {
  it("arrives in the composer unsent, with the user in front of it", () => {
    mount(<Composer />)

    act(() => shell.dispatch({ type: "ask", text: "Vì sao VN-INDEX giảm?" }))

    expect(shell.state.view).toBe("chat")
    expect(screen.getByLabelText("Ask Alpha Desk")).toHaveValue("Vì sao VN-INDEX giảm?")
    // Offered, not asked. Nothing was submitted on the reader's behalf.
    expect(desk.submit).not.toHaveBeenCalled()
  })

  it("survives a switch between the opening screen and the docked composer", () => {
    // The draft lives in the shell rather than in the field, so the two
    // surfaces that mount a composer are the same composer as far as the user
    // is concerned.
    const { rerender } = mount(<Composer variant="opening" />)

    fireEvent.change(screen.getByLabelText("Ask Alpha Desk"), {
      target: { value: "nửa câu" },
    })

    rerender(
      <ShellProvider>
        <Probe />
        <Composer />
      </ShellProvider>,
    )

    expect(shell.state.draft).toBe("nửa câu")
  })
})

describe("the composer", () => {
  it("sends what was typed and clears the field", () => {
    mount(<Composer />)

    const field = screen.getByLabelText("Ask Alpha Desk")
    fireEvent.change(field, { target: { value: "FPT thế nào?" } })
    fireEvent.submit(field.closest("form")!)

    expect(desk.submit).toHaveBeenCalledWith("FPT thế nào?")
    expect(shell.state.draft).toBe("")
  })

  it("keeps the field open while a Turn runs, and offers Stop instead of Send", () => {
    // Composing the next question while an answer arrives is the ordinary way
    // anyone uses a conversation; locking the box would make this a form.
    desk.canCancel = true
    mount(<Composer />)

    expect(screen.getByLabelText("Ask Alpha Desk")).not.toBeDisabled()
    expect(screen.queryByRole("button", { name: /^send$/i })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument()
  })

  it("goes inert the moment Stop is pressed, before the terminal event", () => {
    desk.canCancel = true
    desk.isCancelling = true
    mount(<Composer />)

    expect(screen.getByRole("button", { name: /cancelling/i })).toBeDisabled()
  })

  it("drops the analysis context without touching the Watchlist", () => {
    mount(<Composer />)

    act(() => shell.dispatch({ type: "context-symbol", symbol: "FPT" }))
    fireEvent.click(screen.getByRole("button", { name: /Bỏ ngữ cảnh/ }))

    expect(shell.state.contextSymbol).toBeNull()
  })
})

describe("what a question can be done with again", () => {
  const asked = { kind: "user", key: "u1", text: "VCB thế nào?", pending: false }

  it("offers the sentence back to the composer instead of editing the message", () => {
    // A message is immutable in the store. Sửa puts the question in the field
    // *unsent*; what leaves is a new question, and the one already asked stays.
    // `ChatView` docks its own composer, which is the field this lands in.
    desk.entries = [asked]
    mount(<ChatView />)

    fireEvent.click(screen.getByRole("button", { name: "Sửa câu hỏi" }))

    expect(screen.getByLabelText("Ask Alpha Desk")).toHaveValue("VCB thế nào?")
    expect(desk.submit).not.toHaveBeenCalled()
    expect(desk.resend).not.toHaveBeenCalled()
  })

  it("asks it again from the message itself", () => {
    desk.entries = [asked]
    mount(<ChatView />)

    fireEvent.click(screen.getByRole("button", { name: "Gửi lại" }))

    expect(desk.resend).toHaveBeenCalledWith("VCB thế nào?")
  })

  it("goes inert while a Turn is running, as the composer does", () => {
    desk.entries = [asked]
    desk.canCancel = true
    mount(<ChatView />)

    expect(screen.getByRole("button", { name: "Gửi lại" })).toBeDisabled()
  })

  it("offers nothing on a question the backend has not confirmed yet", () => {
    desk.entries = [{ ...asked, pending: true }]
    mount(<ChatView />)

    expect(screen.queryByRole("button", { name: "Gửi lại" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Sao chép" })).not.toBeInTheDocument()
  })
})

describe("an admission refusal", () => {
  it("is shown as its own sentence beside the transcript, never over it", () => {
    // A 429 or a 503 is an HTTP outcome carrying a stable reason, never an
    // event, and never a reason to clear what is on screen.
    desk.entries = [{ kind: "user", key: "u1", text: "hỏi gì đó", pending: false }]
    desk.refusal = "Bạn đang có một lượt đang chạy."
    mount(<ChatView />)

    expect(screen.getByRole("alert")).toHaveTextContent(/một lượt đang chạy/)
    expect(screen.getByText("hỏi gì đó")).toBeInTheDocument()
  })
})

describe("the conversation's own scroll", () => {
  it("gives the transcript the overflow, so the composer stays on the floor", () => {
    desk.entries = [{ kind: "user", key: "u1", text: "hỏi", pending: false }]
    const { container } = mount(<ChatView />)

    const scroller = container.querySelector(".overflow-y-auto")
    expect(scroller).not.toBeNull()
    expect(scroller?.textContent).toContain("hỏi")
  })

  it("never lets the page body scroll sideways", () => {
    desk.entries = [{ kind: "user", key: "u1", text: "hỏi", pending: false }]
    const { container } = mount(<ChatView />)

    for (const element of container.querySelectorAll("div")) {
      expect(element.className).not.toMatch(/\boverflow-x-scroll\b/)
    }
  })
})
