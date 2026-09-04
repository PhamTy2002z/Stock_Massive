// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { act, cleanup, render } from "@testing-library/react"

import {
  chatColumnWidth,
  inspectorWidth,
  ShellProvider,
  sidebarFloats,
  useShell,
} from "./shell-state"

afterEach(cleanup)

beforeEach(() => {
  window.localStorage.clear()
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: 1440,
  })
})

let shell: ReturnType<typeof useShell>

function Probe() {
  shell = useShell()
  return null
}

function mount() {
  render(
    <ShellProvider>
      <Probe />
    </ShellProvider>,
  )
}

describe("the chat-first workspace", () => {
  it("opens on the conversation with the desk off", () => {
    mount()

    // The desk is a mode the reader turns on from the composer, so a shell that
    // opened with it already on would be answering a question nobody asked.
    expect(shell.state.view).toBe("chat")
    expect(shell.state.inspector).toBeNull()
    expect(shell.state.signalDesk).toBe(false)
  })

  it("turning the desk on opens the pane beside the conversation", () => {
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(shell.state.signalDesk).toBe(true)
    expect(shell.state.inspector).toBe("deskView")
    expect(inspectorWidth(shell.state)).toBeGreaterThan(0)
  })

  it("opens sources for the message that requested them", () => {
    mount()

    act(() => shell.dispatch({ type: "open-sources", messageId: 42 }))

    expect(shell.state.inspector).toBe("sources")
    expect(shell.state.sourcesMessageId).toBe(42)
    expect(inspectorWidth(shell.state)).toBeGreaterThan(0)
  })

  it("puts an offered question in the draft without sending it", () => {
    mount()

    act(() => shell.dispatch({ type: "ask", text: "FPT đang có rủi ro gì?" }))

    expect(shell.state.view).toBe("chat")
    expect(shell.state.draft).toBe("FPT đang có rủi ro gì?")
  })
})

describe("layout and overlays", () => {
  it("keeps only the latest overlay", () => {
    mount()

    act(() => shell.dispatch({ type: "overlay", overlay: "account" }))
    act(() => shell.dispatch({ type: "overlay", overlay: "share" }))

    expect(shell.state.overlay).toBe("share")
  })

  it("closes an overlay before closing the inspector", () => {
    mount()
    act(() => shell.dispatch({ type: "open-inspector", tab: "sources" }))
    act(() => shell.dispatch({ type: "overlay", overlay: "palette" }))

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })))
    expect(shell.state.overlay).toBeNull()
    expect(shell.state.inspector).toBe("sources")

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })))
    expect(shell.state.inspector).toBeNull()
  })

  it("opens the command palette from the platform shortcut", () => {
    mount()

    act(() =>
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true })),
    )

    expect(shell.state.overlay).toBe("palette")
  })

  it("folds the sidebar on compact screens", () => {
    mount()

    act(() => shell.dispatch({ type: "viewport", width: 390 }))

    expect(shell.state.sidebarOpen).toBe(false)
    expect(sidebarFloats(shell.state)).toBe(false)
  })

  it("restores and applies the reader's chat width", () => {
    window.localStorage.setItem(
      "alpha-desk.preferences",
      JSON.stringify({ sidebarOpen: true, chatWidth: 680 }),
    )
    mount()

    expect(chatColumnWidth(shell.state)).toBe(680)
  })
})
