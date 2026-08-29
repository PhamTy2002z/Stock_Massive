// @vitest-environment jsdom
/**
 * The chrome above the workspace.
 *
 * Asserted through roles rather than class names: what the header promises is
 * that it names the board on screen, that every other board of the conversation
 * is one dropdown away, and that "Nguồn" is a toggle beside it rather than a
 * panel somewhere else.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SignalDeskBoard } from "@/components/shell/shell-state"
import { BOARD_SWITCHER_COPY, SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"

import { SignalDeskHeader } from "./signal-desk-header"

afterEach(cleanup)

const BOARDS: SignalDeskBoard[] = [
  { artifactId: "a1", title: "STB — thanh khoản trong phiên", symbol: "STB" },
  { artifactId: "a2", title: "HPG — rà soát điều kiện", symbol: "HPG" },
  { artifactId: "a3", title: "Lệch giá sau báo cáo" },
]

function mount(overrides: Partial<Parameters<typeof SignalDeskHeader>[0]> = {}) {
  const props = {
    boards: BOARDS,
    pinned: [] as string[],
    activeDeskViewId: "a3",
    showingSources: false,
    canExport: true,
    menuOpen: false,
    onOpenDeskView: vi.fn(),
    onOpenSources: vi.fn(),
    onToggleMenu: vi.fn(),
    onTogglePin: vi.fn(),
    onOpenSwitcher: vi.fn(),
    onShare: vi.fn(),
    onExport: vi.fn(),
    ...overrides,
  }
  render(<SignalDeskHeader {...props} />)
  return props
}

describe("the board on screen", () => {
  it("names the open board on the one control, and how many there are", () => {
    mount()

    const control = screen.getByRole("button", { name: BOARD_SWITCHER_COPY.open })
    expect(control.textContent).toContain(BOARDS[2].title)
    expect(control.textContent).toContain(BOARD_SWITCHER_COPY.count(3))
    expect(control).toHaveAttribute("aria-haspopup", "menu")
    expect(screen.queryAllByRole("tab")).toHaveLength(0)
  })

  it("asks the reader to choose when nothing is open yet", () => {
    mount({ boards: [], activeDeskViewId: null })

    expect(screen.getByRole("button", { name: BOARD_SWITCHER_COPY.open }).textContent).toBe(
      BOARD_SWITCHER_COPY.choose,
    )
  })

  it("opens the dropdown from the control, not the switcher", () => {
    const props = mount()

    fireEvent.click(screen.getByRole("button", { name: BOARD_SWITCHER_COPY.open }))

    expect(props.onToggleMenu).toHaveBeenCalledWith(true)
    expect(props.onOpenSwitcher).not.toHaveBeenCalled()
  })

  it("lists every board in the dropdown, pinned first, and opens the one pressed", () => {
    const props = mount({ menuOpen: true, pinned: ["a1"] })

    const items = screen.getAllByRole("menuitem").map((item) => item.textContent)
    expect(items[0]).toContain(BOARDS[0].title)
    expect(items.slice(1, BOARDS.length)).toEqual(
      BOARDS.slice(1)
        .reverse()
        .map((board) => board.title + (board.symbol ?? "")),
    )
    expect(screen.getByRole("menu").textContent).toContain(BOARD_SWITCHER_COPY.search)

    fireEvent.click(screen.getByRole("menuitem", { name: new RegExp(BOARDS[1].title) }))
    expect(props.onOpenDeskView).toHaveBeenCalledWith("a2")
    expect(props.onToggleMenu).toHaveBeenCalledWith(false)
  })

  it("pins from the dropdown without opening the board", () => {
    const props = mount({ menuOpen: true })

    fireEvent.click(screen.getAllByRole("button", { name: BOARD_SWITCHER_COPY.pin })[0])
    expect(props.onTogglePin).toHaveBeenCalledWith("a3", true)
    expect(props.onOpenDeskView).not.toHaveBeenCalled()
  })

  it("reaches the searchable switcher from the dropdown's last row", () => {
    const props = mount({ menuOpen: true })

    fireEvent.click(screen.getByRole("menuitem", { name: new RegExp(BOARD_SWITCHER_COPY.search) }))
    expect(props.onOpenSwitcher).toHaveBeenCalled()
    expect(props.onToggleMenu).toHaveBeenCalledWith(false)
  })

  it("closes on a press outside, and stays for a press inside", () => {
    const props = mount({ menuOpen: true })

    fireEvent.pointerDown(screen.getByRole("menu"))
    expect(props.onToggleMenu).not.toHaveBeenCalled()

    fireEvent.pointerDown(document.body)
    expect(props.onToggleMenu).toHaveBeenCalledWith(false)
  })

  it("never shows a reader an id or a recipe slug", () => {
    mount({
      menuOpen: true,
      boards: [{ ...BOARDS[0], studyName: "intraday_liquidity", studyDisplayName: "Thanh khoản trong phiên" }],
    })

    const text = document.body.textContent ?? ""
    expect(text).not.toContain("a1")
    expect(text).not.toContain("intraday_liquidity")
    expect(text).toContain("Thanh khoản trong phiên")
  })
})

describe("the sources beside the board", () => {
  it("is a toggle, not a tab, and opens the sources", () => {
    const props = mount()

    const sources = screen.getByRole("button", { name: SIGNAL_DESK_COPY.sources })
    expect(sources).toHaveAttribute("aria-pressed", "false")
    fireEvent.click(sources)

    expect(props.onOpenSources).toHaveBeenCalled()
  })

  it("is pressed when that is what the pane is showing", () => {
    mount({ showingSources: true })

    expect(screen.getByRole("button", { name: SIGNAL_DESK_COPY.sources })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
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
    mount()

    expect(screen.queryByRole("button", { name: /Lưu/ })).toBeNull()
  })
})
