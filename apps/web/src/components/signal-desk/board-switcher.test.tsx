// @vitest-environment jsdom
/**
 * Finding one board among twenty.
 *
 * Asserted through what a reader does — type a few letters, press down, press
 * Enter — rather than through the row-building function alone, because the
 * failure this surface exists to prevent is a keyboard that stops halfway.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SignalDeskBoard } from "@/components/shell/shell-state"
import { BOARD_SWITCHER_COPY } from "@/lib/alpha-desk/copy"

import { BoardSwitcher, normalise } from "./board-switcher"

afterEach(cleanup)

const BOARDS: SignalDeskBoard[] = [
  {
    artifactId: "a1",
    title: "Thanh khoản trong phiên — STB",
    symbol: "STB",
    studyName: "intraday_liquidity",
    studyDisplayName: "Thanh khoản trong phiên",
    round: 1,
  },
  {
    artifactId: "a2",
    title: "Điều kiện hiện tại — HPG",
    symbol: "HPG",
    studyName: "entry_condition_review",
    studyDisplayName: "Rà soát điều kiện",
    round: 2,
  },
  {
    artifactId: "a3",
    title: "Lệch giá sau báo cáo",
    studyName: "earnings_dislocation",
    studyDisplayName: "Lệch giá sau báo cáo",
    round: 3,
  },
]

function mount(overrides: Partial<Parameters<typeof BoardSwitcher>[0]> = {}) {
  const props = {
    boards: BOARDS,
    pinned: [] as string[],
    activeBoardId: "a3",
    onOpenBoard: vi.fn(),
    onTogglePin: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  }
  render(<BoardSwitcher {...props} />)
  return props
}

const field = () => screen.getByRole("combobox")
const rows = () => screen.getAllByRole("option")

describe("searching", () => {
  it("finds a board by its ticker", () => {
    mount()

    fireEvent.change(field(), { target: { value: "hpg" } })

    expect(rows()).toHaveLength(1)
    expect(rows()[0].textContent).toContain("Điều kiện hiện tại — HPG")
  })

  it("finds a board by the name of the analysis that drew it", () => {
    mount()

    fireEvent.change(field(), { target: { value: "rà soát" } })

    expect(rows()).toHaveLength(1)
    expect(rows()[0].textContent).toContain("HPG")
  })

  it("does not make the reader type the accents", () => {
    mount()

    fireEvent.change(field(), { target: { value: "thanh khoan" } })

    expect(rows()).toHaveLength(1)
    expect(rows()[0].textContent).toContain("STB")
  })

  it("says so rather than showing an empty box when nothing matches", () => {
    mount()

    fireEvent.change(field(), { target: { value: "vcb" } })

    expect(screen.getByText(BOARD_SWITCHER_COPY.noMatch)).toBeInTheDocument()
  })

  it("names the conversation's own emptiness differently", () => {
    mount({ boards: [] })

    expect(screen.getByText(BOARD_SWITCHER_COPY.empty)).toBeInTheDocument()
  })
})

describe("the keyboard", () => {
  it("opens the board under the cursor and closes behind itself", () => {
    const props = mount()

    fireEvent.keyDown(field(), { key: "ArrowDown" })
    fireEvent.keyDown(field(), { key: "Enter" })

    // Newest first with nothing pinned, so one step down from `a3` is `a2`.
    expect(props.onOpenBoard).toHaveBeenCalledWith("a2")
    expect(props.onClose).toHaveBeenCalled()
  })

  it("wraps rather than sticking at the top", () => {
    const props = mount()

    // Past the end is the row that regroups the list, and the board above it
    // is the oldest one the conversation drew.
    fireEvent.keyDown(field(), { key: "ArrowUp" })
    fireEvent.keyDown(field(), { key: "ArrowUp" })
    fireEvent.keyDown(field(), { key: "Enter" })

    expect(props.onOpenBoard).toHaveBeenCalledWith("a1")
  })

  it("starts over at the first match when the query changes", () => {
    const props = mount()
    fireEvent.keyDown(field(), { key: "ArrowDown" })

    fireEvent.change(field(), { target: { value: "stb" } })
    fireEvent.keyDown(field(), { key: "Enter" })

    expect(props.onOpenBoard).toHaveBeenCalledWith("a1")
  })
})

describe("everything the conversation drew", () => {
  it("offers the way to the list grouped by question", () => {
    mount()

    expect(screen.getByText(BOARD_SWITCHER_COPY.showAll)).toBeInTheDocument()
  })

  it("offers nothing to regroup in a conversation that drew nothing", () => {
    mount({ boards: [] })

    expect(screen.queryByText(BOARD_SWITCHER_COPY.showAll)).toBeNull()
  })

  it("groups by the question that drew them", () => {
    mount()

    fireEvent.change(field(), { target: { value: "*" } })

    expect(screen.getByText(BOARD_SWITCHER_COPY.round(1))).toBeInTheDocument()
    expect(screen.getByText(BOARD_SWITCHER_COPY.round(3))).toBeInTheDocument()
    expect(rows()).toHaveLength(3)
  })
})

describe("pinning from the list", () => {
  it("asks for the pin the row does not have", () => {
    const props = mount()

    fireEvent.click(screen.getAllByRole("button", { name: BOARD_SWITCHER_COPY.pin })[0])

    expect(props.onTogglePin).toHaveBeenCalledWith("a3", true)
  })

  it("offers to release one that has it, and lists it first", () => {
    const props = mount({ pinned: ["a1"] })

    expect(rows()[0].textContent).toContain("STB")
    fireEvent.click(screen.getByRole("button", { name: BOARD_SWITCHER_COPY.unpin }))

    expect(props.onTogglePin).toHaveBeenCalledWith("a1", false)
  })
})

describe("what a row is allowed to show", () => {
  it("never prints the slug the server keys the recipe under", () => {
    const { container } = render(
      <BoardSwitcher
        boards={BOARDS}
        pinned={[]}
        activeBoardId={null}
        onOpenBoard={vi.fn()}
        onTogglePin={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const text = container.textContent ?? ""
    for (const board of BOARDS) {
      expect(text).not.toContain(board.studyName)
      expect(text).not.toContain(board.artifactId)
    }
  })

  it("still finds a board by that slug, for a reader who pasted one", () => {
    mount()

    fireEvent.change(field(), { target: { value: "earnings_dislocation" } })

    expect(rows()).toHaveLength(1)
    expect(rows()[0].textContent).toContain("Lệch giá sau báo cáo")
  })
})

describe("normalise", () => {
  it("folds case, tone marks and the stroked d", () => {
    expect(normalise("Điều Kiện")).toBe("dieu kien")
  })
})
