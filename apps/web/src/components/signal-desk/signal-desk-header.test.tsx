// @vitest-environment jsdom
/**
 * The chrome above the workspace.
 *
 * Asserted through roles rather than class names: what the strip promises is
 * that every desk view of a conversation stays reachable and that "Nguồn" is one
 * of the tabs rather than a panel somewhere else — both of which a reader
 * experiences as tabs they can reach, not as markup.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SignalDeskTab } from "@/components/shell/shell-state"

import { SignalDeskHeader } from "./signal-desk-header"

afterEach(cleanup)

const DESK_VIEWS: SignalDeskTab[] = [
  { artifactId: "a1", title: "STB — thanh khoản trong phiên" },
  { artifactId: "a2", title: "HPG — rà soát điều kiện" },
  { artifactId: "a3", title: "Lệch giá sau báo cáo" },
]

function mount(overrides: Partial<Parameters<typeof SignalDeskHeader>[0]> = {}) {
  const props = {
    deskViews: DESK_VIEWS,
    activeDeskViewId: "a3",
    showingSources: false,
    canExport: true,
    onOpenDeskView: vi.fn(),
    onCloseDeskView: vi.fn(),
    onOpenSources: vi.fn(),
    onShare: vi.fn(),
    onExport: vi.fn(),
    ...overrides,
  }
  render(<SignalDeskHeader {...props} />)
  return props
}

describe("the tab strip", () => {
  it("keeps a tab for every desk view the conversation drew", () => {
    // The bug it exists for: one artifact id meant the third Study made the
    // first two unreachable.
    mount()

    const tabs = screen.getAllByRole("tab")
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      ...DESK_VIEWS.map((deskView) => deskView.title),
      "Nguồn",
    ])
  })

  it("marks exactly one tab as the open one", () => {
    mount()

    const selected = screen.getAllByRole("tab").filter(
      (tab) => tab.getAttribute("aria-selected") === "true",
    )
    expect(selected).toHaveLength(1)
    expect(selected[0]).toHaveTextContent("Lệch giá sau báo cáo")
  })

  it("opens an earlier deskView the reader clicks back to", () => {
    const props = mount()

    fireEvent.click(screen.getByRole("tab", { name: /thanh khoản/ }))

    expect(props.onOpenDeskView).toHaveBeenCalledWith("a1")
  })

  it("keeps the sources of an answer reachable from the same strip", () => {
    // Nothing that existed before the redesign may become unreachable by it.
    const props = mount()

    fireEvent.click(screen.getByRole("tab", { name: "Nguồn" }))

    expect(props.onOpenSources).toHaveBeenCalled()
  })

  it("marks the sources tab open when that is what the pane is showing", () => {
    mount({ showingSources: true, activeDeskViewId: null })

    expect(screen.getByRole("tab", { name: "Nguồn" })).toHaveAttribute(
      "aria-selected",
      "true",
    )
  })

  it("offers to close a desk view but never the sources", () => {
    // Sources is not a desk view; there is nothing there to close.
    mount()

    expect(screen.getAllByRole("button", { name: /^Close / })).toHaveLength(
      DESK_VIEWS.length,
    )
  })

  it("closes the desk view whose control was pressed", () => {
    const props = mount()

    fireEvent.click(screen.getByRole("button", { name: "Close HPG — rà soát điều kiện" }))

    expect(props.onCloseDeskView).toHaveBeenCalledWith("a2")
  })
})

describe("the way out to a file", () => {
  it("opens sharing from the right-hand header", () => {
    const props = mount()

    fireEvent.click(screen.getByRole("button", { name: "Chia sẻ" }))

    expect(props.onShare).toHaveBeenCalled()
  })

  it("writes the desk view on screen", () => {
    const props = mount()

    fireEvent.click(screen.getByRole("button", { name: /Xuất/ }))

    expect(props.onExport).toHaveBeenCalled()
  })

  it("waits until there are numbers to write", () => {
    mount({ canExport: false })

    expect(screen.getByRole("button", { name: /Xuất/ })).toBeDisabled()
  })

  it("offers no save, because nothing would keep it", () => {
    // There is no endpoint behind a saved report, and a control that swallowed
    // the press would tell a reader their work was kept.
    mount()

    expect(screen.queryByRole("button", { name: /Lưu/ })).toBeNull()
  })
})
