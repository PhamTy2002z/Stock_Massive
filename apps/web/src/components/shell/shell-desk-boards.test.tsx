// @vitest-environment jsdom
/**
 * What a conversation's boards promise once it has made more than a few.
 *
 * The rule being tested is that the record is complete and its order is stable:
 * nothing a Turn drew ever leaves the list while the Thread is on screen,
 * pinning holds a board at the top of it, and neither reopening the Thread nor
 * pressing a board rearranges what the reader was looking at.
 */

import { act, cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ShellProvider, useShell, type SignalDeskBoard } from "./shell-state"

afterEach(cleanup)

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
  act(() => shell.dispatch({ type: "viewport", width: 1600 }))
}

/** Announce `count` boards, oldest first, the way a Turn does. */
function announce(count: number): void {
  for (let index = 1; index <= count; index += 1) {
    act(() =>
      shell.dispatch({
        type: "signal-desk-ready",
        artifactId: `a${index}`,
        title: `bảng ${index}`,
        round: index,
      }),
    )
  }
}

const boards = () => shell.state.deskBoards.map((board) => board.artifactId)

describe("a conversation that keeps drawing", () => {
  it("keeps every board it drew, in the order it drew them", () => {
    mount()

    announce(8)

    expect(boards()).toEqual(["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"])
    // The same boards newest first, which is what the desk lands on.
    expect(shell.state.deskRecent[0]).toBe("a8")
  })

  it("opens a board the reader picked out of a long conversation", () => {
    mount()
    announce(8)

    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "a1" }))

    expect(shell.state.deskViewArtifactId).toBe("a1")
    // Pressing a board must not move it: a list that reorders under the press
    // makes the next press land on something else.
    expect(shell.state.deskRecent[0]).toBe("a8")
    expect(boards()).toHaveLength(8)
  })

  it("files a board it meets for the first time on a card in the transcript", () => {
    // The transcript is read before the boards are restored off it, so a card
    // can name a picture this state has never seen.
    mount()

    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "a9", title: "bảng 9" }))

    expect(boards()).toEqual(["a9"])
    expect(shell.state.deskRecent).toEqual(["a9"])
  })
})

describe("pinning a board", () => {
  it("records the pins in the order they were made", () => {
    mount()
    announce(4)

    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a2", pinned: true }))
    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a1", pinned: true }))

    expect(shell.state.deskPinned).toEqual(["a2", "a1"])
  })

  it("leaves the rest of the list where it was when a pin is released", () => {
    mount()
    announce(6)
    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a1", pinned: true }))
    const order = [...shell.state.deskRecent]

    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a1", pinned: false }))

    expect(shell.state.deskPinned).toEqual([])
    expect(shell.state.deskRecent).toEqual(order)
  })

  it("is inert when the pin already says what it is being told", () => {
    mount()
    announce(2)
    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a1", pinned: true }))
    const settled = shell.state

    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a1", pinned: true }))

    expect(shell.state).toBe(settled)
  })

  it("holds a pin restored before the board it names has arrived", () => {
    // Pins come out of this browser; boards come out of the Thread's messages.
    // The order the two land in is not something either side controls.
    mount()
    act(() => shell.dispatch({ type: "desk-pins-restored", artifactIds: ["a7"] }))

    expect(shell.state.deskBoards).toEqual([])

    announce(8)

    expect(shell.state.deskPinned).toEqual(["a7"])
    expect(boards()).toContain("a7")
  })

  it("forgets the pins with the conversation they belonged to", () => {
    mount()
    announce(3)
    act(() => shell.dispatch({ type: "pin-desk-view", artifactId: "a1", pinned: true }))

    act(() => shell.dispatch({ type: "thread", signalDesk: false, opened: true }))

    expect(shell.state.deskPinned).toEqual([])
    expect(shell.state.deskBoards).toEqual([])
    expect(shell.state.deskRecent).toEqual([])
  })
})

describe("what a board is filed under", () => {
  it("keeps the ticker and the analysis, so the switcher can find it again", () => {
    mount()

    act(() =>
      shell.dispatch({
        type: "signal-desk-ready",
        artifactId: "a1",
        title: "Thanh khoản trong phiên — STB",
        symbol: "STB",
        studyName: "intraday_liquidity",
        studyDisplayName: "Thanh khoản trong phiên",
        round: 2,
      }),
    )

    expect(shell.state.deskBoards[0]).toEqual<SignalDeskBoard>({
      artifactId: "a1",
      title: "Thanh khoản trong phiên — STB",
      symbol: "STB",
      studyName: "intraday_liquidity",
      studyDisplayName: "Thanh khoản trong phiên",
      round: 2,
    })
  })

  it("does not lose what it knew to a later announcement that says less", () => {
    mount()
    act(() =>
      shell.dispatch({
        type: "signal-desk-ready",
        artifactId: "a1",
        title: "Thanh khoản trong phiên — STB",
        symbol: "STB",
      }),
    )

    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "a1" }))

    expect(shell.state.deskBoards[0].symbol).toBe("STB")
    expect(shell.state.deskBoards[0].title).toBe("Thanh khoản trong phiên — STB")
  })

  it("re-renders nothing when the message list restates what it already holds", () => {
    const tabs: SignalDeskBoard[] = [
      { artifactId: "a1", title: "một", round: 1 },
      { artifactId: "a2", title: "hai", round: 2 },
    ]
    mount()
    act(() => shell.dispatch({ type: "desk-views-restored", tabs }))
    const settled = shell.state

    act(() => shell.dispatch({ type: "desk-views-restored", tabs }))

    expect(shell.state).toBe(settled)
  })

  it("adds what a reopen brought without reordering what was already there", () => {
    // The message list re-announces every board on each change, and the reader
    // is looking at the list while it does.
    mount()
    announce(3)

    act(() =>
      shell.dispatch({
        type: "desk-views-restored",
        tabs: [
          { artifactId: "a1", title: "bảng 1" },
          { artifactId: "a2", title: "bảng 2" },
          { artifactId: "a3", title: "bảng 3" },
          { artifactId: "a4", title: "bảng 4" },
        ],
      }),
    )

    expect(boards()).toEqual(["a1", "a2", "a3", "a4"])
    expect(shell.state.deskRecent).toEqual(["a4", "a3", "a2", "a1"])
  })
})

describe("⌘K", () => {
  it("opens the board switcher while the workspace is on screen", () => {
    mount()
    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))
    })

    expect(shell.state.overlay).toBe("boards")
  })

  it("still opens the conversation search everywhere else", () => {
    mount()

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))
    })

    expect(shell.state.overlay).toBe("palette")
  })
})
