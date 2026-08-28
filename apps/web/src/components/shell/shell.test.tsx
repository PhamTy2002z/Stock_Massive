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

import type { Failure } from "@/lib/failure"

const queryMock = vi.hoisted(() => ({
  detailError: false,
  detailFetching: false,
  threadsError: false,
  refetch: vi.fn(),
  monitorOverview: {
    meta: {
      exchange: "ALL",
      as_of: "2026-08-24T00:00:00+07:00",
      generated_at: "2026-08-24T09:00:00Z",
      state: "complete",
      coverage: { eligible: 1, evaluated: 1, missing: 0, state: "complete" },
      realtime_coverage: null,
      sources: [],
      issues: [],
      method_versions: { breadth: "breadth-v1" },
    },
    indices: [],
    breadth: {
      advancing: { value: 1, unit: "symbol", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
      declining: { value: 0, unit: "symbol", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
      unchanged: { value: 0, unit: "symbol", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
      advance_decline_ratio: { value: null, unit: "ratio", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: ["declining_zero"] },
      above_ma20_pct: { value: 100, unit: "%", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
      above_ma50_pct: { value: 100, unit: "%", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
      above_ma200_pct: { value: 100, unit: "%", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
    },
    liquidity: { value: 1.2, unit: "ratio", as_of: "2026-08-24T00:00:00+07:00", method: "breadth-v1", issues: [] },
    foreign_flow: { value: 1_000_000, unit: "VND", as_of: "2026-08-24T00:00:00+07:00", method: "foreign-flow-v1", issues: [] },
    active_flow_over_adtv: { value: null, unit: "ratio", as_of: "2026-08-24T00:00:00+07:00", method: "dnse-active-flow-v1", issues: ["realtime_projection_unavailable"] },
    valuation: {
      market_pe: { value: 14, unit: "ratio", as_of: "2026-08-24T00:00:00+07:00", method: "valuation-regime-v1", issues: [] },
      market_pb: { value: 1.8, unit: "ratio", as_of: "2026-08-24T00:00:00+07:00", method: "valuation-regime-v1", issues: [] },
      pe_percentile: { value: 60, unit: "%", as_of: "2026-08-24T00:00:00+07:00", method: "valuation-regime-v1", issues: [] },
      pb_percentile: { value: 55, unit: "%", as_of: "2026-08-24T00:00:00+07:00", method: "valuation-regime-v1", issues: [] },
      coverage: { eligible: 1, evaluated: 1, missing: 0, state: "complete" },
    },
    leading_sectors: [],
    lagging_sectors: [],
    notable_stocks: [{
      symbol: "FPT",
      name: "Công ty Cổ phần FPT",
      exchange: "HOSE",
      sector_code: "10",
      sector_name: "Công nghệ",
      metrics: { return_1d_pct: { value: 1.2, unit: "%", as_of: "2026-08-24T00:00:00+07:00", method: "stock-screen-v1", issues: [] } },
      trend: {},
      issues: [],
    }],
  },
}))

vi.mock("@tanstack/react-query", () => ({
  useInfiniteQuery: () => ({
    data: undefined,
    isError: false,
    isFetching: false,
    isFetchingNextPage: false,
    isPending: false,
    hasNextPage: false,
    fetchNextPage: vi.fn(),
    refetch: vi.fn(),
  }),
  useQuery: ({ queryKey }: { queryKey: readonly unknown[] }) =>
    queryKey[0] === "market" && queryKey[1] === "monitor" && queryKey[2] === "overview"
      ? {
          data: queryMock.monitorOverview,
          isError: false,
          isFetching: false,
          isPending: false,
          refetch: vi.fn(),
        }
      : queryKey[0] === "threads"
      ? {
          data: undefined,
          isError: queryMock.threadsError,
          error: queryMock.threadsError ? new TypeError("Failed to fetch") : null,
          isFetching: false,
          isPending: false,
          refetch: vi.fn(),
        }
      : queryKey[queryKey.length - 1] === "detail"
      ? {
          data: undefined,
          isError: queryMock.detailError,
          isFetching: queryMock.detailFetching,
          isPending: false,
          refetch: queryMock.refetch,
        }
      : {
          data: undefined,
          isError: false,
          isFetching: false,
          isPending: false,
          refetch: vi.fn(),
        },
}))

vi.mock("@/hooks/use-market-indices", () => ({
  useMarketIndices: () => ({ data: [], isPending: false }),
}))

// The Greeting in the empty conversation view reads the signed-in account.
// The shell test cares about the layout, not the account query, so the auth
// call is faked into a settled, signed-out state — enough for the plain
// English line to render deterministically.
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: null, isPending: false, isSigningOut: false }),
}))

vi.mock("@/hooks/use-sector-performance", () => ({
  useSectorPerformance: () => ({ data: { sectors: [] }, isPending: false }),
}))

vi.mock("@/hooks/use-vn30-overview", () => ({
  useVN30Overview: () => ({
    data: {
      stocks: [
        {
          symbol: "FPT",
          company_name: "Công ty Cổ phần FPT",
          price: 123_000,
          change_pct: 1.2,
          volume: 1_000_000,
        },
      ],
    },
    isPending: false,
  }),
}))

vi.mock("@/hooks/use-price-board", () => ({
  indexBySymbol: () => new Map(),
  usePriceBoard: () => ({ data: [] }),
}))

vi.mock("@/hooks/use-price-history", () => ({
  usePriceHistory: () => ({ data: [], isPending: false }),
}))

const desk = {
  threadId: null as string | null,
  entries: [] as unknown[],
  canCancel: false,
  isCancelling: false,
  isSubmitting: false,
  refusal: null as string | null,
  refusalFailure: null as Failure | null,
  flagFailedFor: null as number | null,
  signalDesk: false,
  setSignalDesk: vi.fn(),
  building: null as string | null,
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
import { Inspector } from "./inspector"
import { focusableElements, Overlays } from "./overlays"
import { MenuItem, SampleDataNote, UnavailableNote } from "./primitives"
import { Conversations } from "./sidebar"
import { SIGNAL_DESK_STARTERS } from "@/lib/alpha-desk/copy"

import { ChatView } from "./view-chat"
import {
  chatColumnWidth,
  inspectorWidth,
  maxChatWidth,
  SIDEBAR_WIDTH,
  ShellProvider,
  sidebarFloats,
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
  desk.signalDesk = false
  desk.building = null
  desk.setSignalDesk.mockClear()
  desk.submit.mockClear()
  desk.cancel.mockClear()
  desk.resend.mockClear()
  queryMock.detailError = false
  queryMock.detailFetching = false
  queryMock.threadsError = false
  queryMock.refetch.mockReset()
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

describe("the Signal Desk against the sidebar", () => {
  it("folds the sidebar when the workspace enters a mobile viewport", () => {
    setViewport(390)
    mount()

    expect(shell.state.sidebarOpen).toBe(false)
  })

  it("folds the sidebar rather than crushing the conversation", () => {
    // 1024 − 274 (sidebar) leaves 750px for two columns that need 380 + 480
    // between them.
    setViewport(1024)
    mount()

    expect(shell.state.sidebarOpen).toBe(true)

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))

    expect(shell.state.inspector).toBe("market")
    expect(shell.state.sidebarOpen).toBe(false)
  })

  it("folds the sidebar when the desk is switched on, however wide the screen", () => {
    // 1600 − 274 clears 380 + 480 with room to spare, so nothing here is the
    // cramped rule: the desk folds the list because it is the desk.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(shell.state.sidebarOpen).toBe(false)
  })

  it("leaves the folded sidebar folded when the desk is switched back off", () => {
    // Reopening it would be a guess about what the reader wanted next, and the
    // corner mark is one click away.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "signal-desk", on: false }))

    expect(shell.state.sidebarOpen).toBe(false)
  })

  it("leaves the sidebar alone when all three columns fit", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "market" }))

    expect(shell.state.sidebarOpen).toBe(true)
  })

  it("gives the desk the majority of the width and pins the conversation", () => {
    // The inversion this redesign is: the chat is the fixed column now, and
    // the workspace is whatever is left rather than the other way round.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))

    expect(chatColumnWidth(shell.state)).toBe(427)
    expect(inspectorWidth(shell.state)).toBeGreaterThan(chatColumnWidth(shell.state))
  })

  it.each([1600, 1280, 1024, 390])("fits inside a %ipx viewport", (width) => {
    setViewport(width)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))

    // A list that floats is worth no width either: with the pane open it lies
    // over the workspace rather than beside it, exactly as the pane itself does
    // on a phone. What this invariant is about is the columns, and a floating
    // rail is not one.
    const sidebar =
      shell.state.sidebarOpen && !sidebarFloats(shell.state) ? SIDEBAR_WIDTH : 0
    // On a phone the pane overlays rather than splits, so it is worth no width
    // and the conversation keeps the screen.
    expect(sidebar + chatColumnWidth(shell.state) + inspectorWidth(shell.state)).toBeLessThanOrEqual(
      width,
    )
  })

  it("clamps a drag to a width that leaves the desk room", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))
    act(() => shell.dispatch({ type: "resize-chat", width: 99_999 }))

    expect(chatColumnWidth(shell.state)).toBe(maxChatWidth(shell.state))
    expect(inspectorWidth(shell.state)).toBe(480)
  })

  it("refuses to drag the conversation narrower than its own minimum", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))
    act(() => shell.dispatch({ type: "resize-chat", width: 10 }))

    expect(chatColumnWidth(shell.state)).toBe(380)
  })

  it("forgets a dragged width when the pane closes", () => {
    // A pane reopened at yesterday's drag width would be a setting nobody
    // asked to keep.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))
    act(() => shell.dispatch({ type: "resize-chat", width: 700 }))
    act(() => shell.dispatch({ type: "close-inspector" }))
    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))

    expect(chatColumnWidth(shell.state)).toBe(427)
  })

  it("is worth nothing at all while it is closed", () => {
    setViewport(1600)
    mount()

    expect(inspectorWidth(shell.state)).toBe(0)
  })
})

describe("the Signal Desk as a mode", () => {
  it("opens the workspace the moment it is switched on, with nothing in it", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(shell.state.signalDesk).toBe(true)
    expect(shell.state.inspector).toBe("deskView")
    expect(shell.state.deskViewArtifactId).toBeNull()
  })

  it("returns to the ordinary chat layout when it is switched off", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "signal-desk", on: false }))

    expect(shell.state.inspector).toBeNull()
    expect(inspectorWidth(shell.state)).toBe(0)
  })

  it("keeps the conversation on a phone rather than taking the screen", () => {
    setViewport(390)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(shell.state.signalDesk).toBe(true)
    expect(shell.state.inspector).toBeNull()
  })

  it("goes off with the pane, so the switch never disagrees with the layout", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "close-inspector" }))

    expect(shell.state.signalDesk).toBe(false)
    expect(shell.state.inspector).toBeNull()
  })

  it("restores the arriving conversation's own answer, never the last one's", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "artifact-1" }))
    act(() => shell.dispatch({ type: "thread", signalDesk: false, opened: true }))

    expect(shell.state.signalDesk).toBe(false)
    expect(shell.state.inspector).toBeNull()
    // The pictures belonged to the conversation being left.
    expect(shell.state.deskViews).toEqual([])
    expect(shell.state.deskViewArtifactId).toBeNull()
  })

  it("opens straight onto a conversation that was left with the desk on", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "thread", signalDesk: true, opened: false }))

    expect(shell.state.signalDesk).toBe(true)
    expect(shell.state.inspector).toBe("deskView")
  })

  it("folds the list when the reader picks a conversation whose desk is on", () => {
    // Wide enough that nothing forces the fold: 1600 − 274 clears 380 + 480,
    // so this has to be the deliberate rule rather than the cramped one.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "thread", signalDesk: true, opened: true }))

    expect(shell.state.sidebarOpen).toBe(false)
    expect(shell.state.inspector).toBe("deskView")
  })

  it("leaves the list alone when the picked conversation has no desk", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "thread", signalDesk: false, opened: true }))

    expect(shell.state.sidebarOpen).toBe(true)
  })

  it("keeps the list through a restore, so nothing slides away after the paint", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "thread", signalDesk: true, opened: false }))

    expect(shell.state.sidebarOpen).toBe(true)
  })
})

describe("the list over an open workspace", () => {
  it("stops taking width from two columns already at their minimums", () => {
    // The report: pulling the list out over an open desk squeezed the
    // conversation and the chart into whatever was left. Floating, it costs
    // them nothing — the widths are the ones they would have had with the list
    // closed.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "open-inspector", tab: "deskView" }))
    const chatAlone = chatColumnWidth(shell.state)
    const deskAlone = inspectorWidth(shell.state)

    act(() => shell.dispatch({ type: "toggle-sidebar" }))
    act(() => shell.dispatch({ type: "toggle-sidebar" }))

    expect(shell.state.sidebarOpen).toBe(true)
    expect(sidebarFloats(shell.state)).toBe(true)
    expect(chatColumnWidth(shell.state)).toBe(chatAlone)
    expect(inspectorWidth(shell.state)).toBe(deskAlone)
  })

  it("stays a column while it is the only thing beside the conversation", () => {
    // With no pane open there is nothing to lie over: the list is part of the
    // workspace and the conversation takes what is left, as it always did.
    setViewport(1600)
    mount()

    expect(shell.state.sidebarOpen).toBe(true)
    expect(sidebarFloats(shell.state)).toBe(false)
  })

  it("floats on a phone, where 274 of 390 was never a column", () => {
    setViewport(390)
    mount()
    act(() => shell.dispatch({ type: "toggle-sidebar" }))

    expect(sidebarFloats(shell.state)).toBe(true)
  })
})

describe("reopening a conversation that already made pictures", () => {
  const TABS = [
    { artifactId: "artifact-1", title: "Thanh khoản STB" },
    { artifactId: "artifact-2", title: "Điều kiện hiện tại — STB" },
  ]

  it("puts the strip back, so the pictures are one click away rather than a scroll", () => {
    // The report this was built from: the reader opens an old conversation, the
    // desk view is right there in the transcript, and the header offers only
    // "Nguồn" — the picture is reachable only by scrolling back to its card.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "thread", signalDesk: true, opened: true }))

    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))

    expect(shell.state.deskViews).toEqual(TABS)
  })

  it("opens the newest one if the reader presses the tab, not the desk's empty state", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))

    expect(shell.state.deskViewArtifactId).toBe("artifact-2")
  })

  it("does not take the screen from a reader who asked for a conversation", () => {
    // Restoring is not announcing. A Thread opened to read its text must not
    // have a third of the window taken by a panel it did not ask for.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "thread", signalDesk: false, opened: true }))

    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))

    expect(shell.state.inspector).toBeNull()
    expect(shell.state.inspectorPinned).toBe(false)
    expect(shell.state.signalDesk).toBe(false)
  })

  it("never pulls a picture out from under the one on screen", () => {
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "artifact-1" }))

    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))

    expect(shell.state.deskViewArtifactId).toBe("artifact-1")
  })

  it("is inert once there is nothing left to put back", () => {
    // It runs on every change to the message list, so a fresh state object each
    // time would re-render the whole shell for nothing.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))
    const settled = shell.state

    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))

    expect(shell.state).toBe(settled)
  })

  it("drops the strip again on the way out to another conversation", () => {
    // The other half of the rule, and the one that already worked: these tabs
    // belong to the conversation being left.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "desk-views-restored", tabs: TABS }))

    act(() => shell.dispatch({ type: "thread", signalDesk: false, opened: true }))

    expect(shell.state.deskViews).toEqual([])
    expect(shell.state.deskViewArtifactId).toBeNull()
  })
})

describe("a desk view arriving mid-answer", () => {
  it("opens on it when the desk is on and the reader is not reading something else", () => {
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    act(() =>
      shell.dispatch({ type: "signal-desk-ready", artifactId: "artifact-1", title: "STB" }),
    )

    expect(shell.state.inspector).toBe("deskView")
    expect(shell.state.deskViewArtifactId).toBe("artifact-1")
    expect(shell.state.deskViews).toEqual([{ artifactId: "artifact-1", title: "STB" }])
  })

  it("files a tab but changes nothing while the desk is off", () => {
    // The mode is the trigger now. An answer must not rearrange the screen
    // under a reader who did not ask it to.
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "artifact-1" }))

    expect(shell.state.inspector).toBeNull()
    expect(shell.state.deskViews).toHaveLength(1)
  })

  it("keeps every desk view of the conversation reachable", () => {
    // The bug this strip exists for: one artifact id meant a Thread that ran
    // three Studies could show only the newest.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a1", title: "one" }))
    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a2", title: "two" }))
    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a3", title: "three" }))

    expect(shell.state.deskViews.map((tab) => tab.artifactId)).toEqual(["a1", "a2", "a3"])
    expect(shell.state.deskViewArtifactId).toBe("a3")

    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "a1" }))

    expect(shell.state.deskViewArtifactId).toBe("a1")
  })

  it("announces one run once, however many times it is republished", () => {
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a1", title: "one" }))
    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a1", title: "one" }))

    expect(shell.state.deskViews).toHaveLength(1)
  })

  it("leaves a tab the reader chose alone, and still files the picture", () => {
    // Auto-open means auto-open *once*. A reader who has deliberately gone to
    // the sources of an answer must not have the pane taken off them by the
    // next round of the same Turn.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "open-sources", messageId: 7 }))

    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "artifact-1" }))

    expect(shell.state.inspector).toBe("sources")
    expect(shell.state.deskViews).toHaveLength(1)
  })

  it("stays out of the way once the reader has put the pane away", () => {
    // A dismissal holds for the conversation. It used to be undone by the very
    // next deskView, which made the close button read as a delay.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "close-inspector" }))

    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "artifact-2" }))

    expect(shell.state.inspector).toBeNull()
  })

  it("never opens the pane by itself on a phone", () => {
    setViewport(390)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "artifact-1" }))

    expect(shell.state.inspector).toBeNull()
    // Still reachable: the card in the transcript is what opens it there.
    expect(shell.state.deskViews).toHaveLength(1)
  })

  it("opens on the picture the reader picked out of the transcript", () => {
    setViewport(1600)
    mount()

    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "artifact-3" }))

    expect(shell.state.signalDesk).toBe(true)
    expect(shell.state.sidebarOpen).toBe(false)
    expect(shell.state.inspector).toBe("deskView")
    expect(shell.state.deskViewArtifactId).toBe("artifact-3")
    expect(shell.state.deskViews).toHaveLength(1)
  })

  it("learns a tab's real name from the row it fetches", () => {
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "open-desk-view", artifactId: "artifact-3" }))

    act(() =>
      shell.dispatch({
        type: "signal-desk-title",
        artifactId: "artifact-3",
        title: "STB — thanh khoản trong phiên",
      }),
    )

    expect(shell.state.deskViews[0].title).toBe("STB — thanh khoản trong phiên")
  })

  it("lands on the neighbour when the open tab is closed", () => {
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a1", title: "one" }))
    act(() => shell.dispatch({ type: "signal-desk-ready", artifactId: "a2", title: "two" }))

    act(() => shell.dispatch({ type: "close-desk-view", artifactId: "a2" }))

    expect(shell.state.deskViews.map((tab) => tab.artifactId)).toEqual(["a1"])
    expect(shell.state.deskViewArtifactId).toBe("a1")
  })
})

describe("the workspace on screen", () => {
  it("opens sharing from its right-hand header", () => {
    setViewport(1600)
    mount(<Inspector />)

    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    fireEvent.click(screen.getByRole("button", { name: "Chia sẻ" }))

    expect(shell.state.overlay).toBe("share")
  })

  it("draws nothing at all while the desk is off", () => {
    setViewport(1600)
    mount(<Inspector />)

    expect(screen.queryByRole("complementary")).toBeNull()
  })

  it("says what will fill it rather than opening blank", () => {
    setViewport(1600)
    mount(<Inspector />)

    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(screen.getByRole("complementary", { name: "Signal Desk" })).toBeInTheDocument()
    expect(screen.getByText(/Signal Desk đang bật/)).toBeInTheDocument()
  })

  it("keeps the sources of an answer one tab away", () => {
    setViewport(1600)
    mount(<Inspector />)

    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    fireEvent.click(screen.getByRole("tab", { name: "Nguồn" }))

    expect(shell.state.inspector).toBe("sources")
  })

  it("resizes the conversation rather than the workspace", () => {
    setViewport(1600)
    mount(<Inspector />)
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    const seam = screen.getByRole("separator", { name: "Resize chat column" })
    expect(seam).toHaveAttribute("aria-valuenow", "427")

    fireEvent.keyDown(seam, { key: "ArrowRight", shiftKey: true })

    expect(chatColumnWidth(shell.state)).toBe(467)
  })

  it("shows the build state while a Study is in flight", () => {
    desk.building = "Dựng hồ sơ thanh khoản STB"
    setViewport(1600)
    mount(<Inspector />)

    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(screen.getByText("Dựng hồ sơ thanh khoản STB")).toBeInTheDocument()
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
    expect(screen.getByLabelText("Hỏi VisgniteAI")).toHaveValue("Vì sao VN-INDEX giảm?")
    // Offered, not asked. Nothing was submitted on the reader's behalf.
    expect(desk.submit).not.toHaveBeenCalled()
  })

  it("survives a switch between the opening screen and the docked composer", () => {
    // The draft lives in the shell rather than in the field, so the two
    // surfaces that mount a composer are the same composer as far as the user
    // is concerned.
    const { rerender } = mount(<Composer variant="opening" />)

    fireEvent.change(screen.getByLabelText("Hỏi VisgniteAI"), {
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

    const field = screen.getByLabelText("Hỏi VisgniteAI")
    fireEvent.change(field, { target: { value: "FPT thế nào?" } })
    fireEvent.submit(field.closest("form")!)

    expect(desk.submit).toHaveBeenCalledWith("FPT thế nào?")
    expect(shell.state.draft).toBe("")
  })

  it("sends on Enter", () => {
    mount(<Composer />)

    const field = screen.getByLabelText("Hỏi VisgniteAI")
    fireEvent.change(field, { target: { value: "FPT thế nào?" } })
    fireEvent.keyDown(field, { key: "Enter" })

    expect(desk.submit).toHaveBeenCalledWith("FPT thế nào?")
  })

  it("leaves Enter to the IME while a Vietnamese syllable is still being composed", () => {
    // Telex and VNI build one syllable out of several keystrokes, and the Enter
    // that commits it is the same Enter that sends. Sending on it would post a
    // half-typed word and swallow the keystroke meant to finish it — on the
    // input method a large share of this product's readers type with.
    mount(<Composer />)

    const field = screen.getByLabelText("Hỏi VisgniteAI")
    fireEvent.change(field, { target: { value: "Vì sao HPG giam" } })
    fireEvent.keyDown(field, { key: "Enter", isComposing: true })

    expect(desk.submit).not.toHaveBeenCalled()

    // And the same key sends once the IME has let go of it.
    fireEvent.keyDown(field, { key: "Enter" })
    expect(desk.submit).toHaveBeenCalledWith("Vì sao HPG giam")
  })

  it("keeps the field open while a Turn runs, and offers Dừng instead of Gửi", () => {
    // Composing the next question while an answer arrives is the ordinary way
    // anyone uses a conversation; locking the box would make this a form.
    desk.canCancel = true
    mount(<Composer />)

    expect(screen.getByLabelText("Hỏi VisgniteAI")).not.toBeDisabled()
    expect(screen.queryByRole("button", { name: "Gửi" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Dừng" })).toBeInTheDocument()
  })

  it("goes inert the moment Dừng is pressed, before the terminal event", () => {
    desk.canCancel = true
    desk.isCancelling = true
    mount(<Composer />)

    expect(screen.getByRole("button", { name: "Đang dừng…" })).toBeDisabled()
  })

  it("drops the analysis context without touching the Watchlist", () => {
    mount(<Composer />)

    act(() => shell.dispatch({ type: "context-symbol", symbol: "FPT" }))
    fireEvent.click(screen.getByRole("button", { name: /Bỏ ngữ cảnh/ }))

    expect(shell.state.contextSymbol).toBeNull()
  })

  it("offers no dead research row in the attach menu", () => {
    // A calque of a competitor's feature name for work this product now does
    // under its own, behind a switch the reader can see.
    mount(<Composer />)

    act(() => shell.dispatch({ type: "overlay", overlay: "attach" }))

    expect(screen.queryByRole("menuitem", { name: /Nghiên cứu sâu/ })).toBeNull()
  })
})

describe("the Signal Desk mode control", () => {
  it("offers both modes by name, not one lit pill", () => {
    // The reason it stopped being a switch: a single lit control tells a reader
    // that something is on and never what the alternative is.
    mount(<Composer />)

    const group = screen.getByRole("radiogroup", { name: "Chế độ trả lời" })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "Chat" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    expect(screen.getByRole("radio", { name: "Signal Desk" })).toHaveAttribute(
      "aria-checked",
      "false",
    )
  })

  it("asks for the mode through the one function that owns it", () => {
    mount(<Composer />)

    fireEvent.click(screen.getByRole("radio", { name: "Signal Desk" }))

    expect(desk.setSignalDesk).toHaveBeenCalledWith(true)
  })

  it("goes back to chat from the other segment", () => {
    desk.signalDesk = true
    mount(<Composer />)

    expect(screen.getByRole("radio", { name: "Signal Desk" })).toHaveAttribute(
      "aria-checked",
      "true",
    )

    fireEvent.click(screen.getByRole("radio", { name: "Chat" }))

    expect(desk.setSignalDesk).toHaveBeenCalledWith(false)
  })

  it("keeps one tab stop, the way a radio group behaves everywhere else", () => {
    mount(<Composer />)

    expect(screen.getByRole("radio", { name: "Chat" })).toHaveAttribute("tabindex", "0")
    expect(screen.getByRole("radio", { name: "Signal Desk" })).toHaveAttribute(
      "tabindex",
      "-1",
    )
  })

  it("becomes the status light while a Study is being built", () => {
    // The same state the pane draws its skeleton from, read in one more place
    // rather than computed a second time.
    desk.signalDesk = true
    desk.building = "Dựng hồ sơ thanh khoản STB"
    mount(<Composer />)

    expect(screen.getByRole("radio", { name: /Đang dựng/ })).toHaveAttribute(
      "aria-busy",
      "true",
    )
  })

  it("says nothing about building while the desk is off", () => {
    desk.building = "Dựng hồ sơ thanh khoản STB"
    mount(<Composer />)

    expect(screen.getByRole("radio", { name: "Signal Desk" })).not.toHaveAttribute(
      "aria-busy",
    )
  })
})

describe("honest incomplete states", () => {
  it("labels unavailable menu actions without removing them", () => {
    render(<MenuItem disabled>Mẫu phân tích</MenuItem>)

    expect(screen.getByRole("menuitem", { name: /Mẫu phân tích/ })).toBeDisabled()
    expect(screen.getByText("Sắp ra mắt")).toBeInTheDocument()
  })

  it("warns before illustrative figures can be treated as evidence", () => {
    render(<SampleDataNote>API chưa phục vụ dữ liệu này.</SampleDataNote>)

    expect(screen.getByText("Dữ liệu minh họa · Không dùng để ra quyết định")).toBeInTheDocument()
    expect(screen.getByText("API chưa phục vụ dữ liệu này.")).toBeInTheDocument()
  })

  it("describes unavailable features without calling them illustrative data", () => {
    render(<UnavailableNote>API chưa có endpoint chia sẻ.</UnavailableNote>)

    expect(screen.getByText("Tính năng sắp ra mắt")).toBeInTheDocument()
    expect(screen.queryByText(/Dữ liệu minh họa/)).not.toBeInTheDocument()
  })

  it("does not tell a reader their conversations are gone when the list failed to load", () => {
    // The worst honest-state bug this product could have: the rail is where a
    // reader confirms their work still exists, and a dropped request used to
    // render there as "Chưa có hội thoại nào" — indistinguishable from having
    // lost everything.
    queryMock.threadsError = true
    mount(<Conversations />)

    expect(screen.queryByText(/Chưa có hội thoại nào/)).not.toBeInTheDocument()
    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Thử lại/ })).toBeInTheDocument()
  })

  it("still says the list is empty when it really is", () => {
    mount(<Conversations />)

    expect(screen.getByText(/Chưa có hội thoại nào/)).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})

describe("dialog focus", () => {
  it("keeps Tab navigation inside the active dialog", () => {
    mount(<Overlays />)
    act(() => shell.dispatch({ type: "overlay", overlay: "share" }))

    const dialog = screen.getByRole("dialog", { name: "Chia sẻ hội thoại" })
    const close = screen.getByRole("button", { name: "Đóng" })
    const team = screen.getByRole("radio", { name: /Chia sẻ nội bộ/ })

    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    team.focus()
    fireEvent.keyDown(team, { key: "Tab" })
    expect(close).toHaveFocus()

    fireEvent.keyDown(close, { key: "Tab", shiftKey: true })
    expect(team).toHaveFocus()
  })

  it("restores focus to the control that opened the dialog", () => {
    mount(
      <>
        <button type="button">Mở chia sẻ</button>
        <Overlays />
      </>,
    )
    const launcher = screen.getByRole("button", { name: "Mở chia sẻ" })
    launcher.focus()

    act(() => shell.dispatch({ type: "overlay", overlay: "share" }))
    fireEvent.click(screen.getByRole("button", { name: "Đóng" }))

    expect(launcher).toHaveFocus()
  })

  it("excludes controls hidden by a responsive ancestor", () => {
    const root = document.createElement("div")
    root.innerHTML = `
      <div style="display: none"><button type="button">Ẩn</button></div>
      <button type="button">Hiện</button>
    `
    document.body.appendChild(root)

    expect(focusableElements(root).map((element) => element.textContent)).toEqual(["Hiện"])

    root.remove()
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

    expect(screen.getByLabelText("Hỏi VisgniteAI")).toHaveValue("VCB thế nào?")
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

describe("the opening the desk gives an empty conversation", () => {
  it("names the product instead of greeting a reader who already said why they came", () => {
    desk.signalDesk = true
    mount(<ChatView />)

    expect(screen.getByText("Signal on your Desk")).toBeInTheDocument()
  })

  it("keeps the ordinary greeting when the desk is off", () => {
    desk.signalDesk = false
    mount(<ChatView />)

    expect(screen.queryByText("Signal on your Desk")).not.toBeInTheDocument()
  })

  it("offers one starter per registered Study, into the field rather than sent", () => {
    // A starter names a symbol, and which symbols exist is a deployment's
    // Universe. The reader gets the sentence to change before it costs a Turn.
    desk.signalDesk = true
    mount(<ChatView />)

    const starter = SIGNAL_DESK_STARTERS[0]
    fireEvent.click(screen.getByRole("button", { name: starter }))

    expect(screen.getByLabelText("Hỏi VisgniteAI")).toHaveValue(starter)
    expect(desk.submit).not.toHaveBeenCalled()
  })

  it("stops offering starters once the conversation has begun", () => {
    desk.signalDesk = true
    desk.entries = [{ kind: "user", key: "u1", text: "hỏi", pending: false }]
    mount(<ChatView />)

    expect(
      screen.queryByRole("button", { name: SIGNAL_DESK_STARTERS[0] }),
    ).not.toBeInTheDocument()
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

/**
 * A reader who arranged the workspace has already said what they want.
 *
 * The distinction under test is which changes count as saying it. A drag and a
 * deliberate collapse do; the fold the shell performs on its own, when three
 * columns will not fit, does not — and persisting that one would leave the
 * sidebar shut for good after a single session on a narrow window.
 */
describe("what the workspace remembers", () => {
  it("brings back a width that was dragged to", () => {
    setViewport(1600)
    mount(<Inspector />)
    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "resize-chat", width: 700 }))
    act(() => shell.dispatch({ type: "dragging", dragging: false }))

    cleanup()
    setViewport(1600)
    mount(<Inspector />)
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(chatColumnWidth(shell.state)).toBe(700)
  })

  it("brings back a sidebar the reader collapsed", () => {
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "toggle-sidebar" }))
    expect(shell.state.sidebarOpen).toBe(false)

    cleanup()
    setViewport(1600)
    mount()

    expect(shell.state.sidebarOpen).toBe(false)
  })

  it("does not remember dismissing the list while it floats", () => {
    // Escape dispatches the same action the collapse button does, but beside an
    // open inspector the list is an overlay — putting it away is closing a
    // surface, not choosing a layout. Persisting it would shut the sidebar for
    // every later session on a wide monitor.
    setViewport(1600)
    mount()
    act(() => shell.dispatch({ type: "open-inspector", tab: "sources" }))
    act(() => shell.dispatch({ type: "toggle-sidebar" }))

    cleanup()
    setViewport(1600)
    mount()

    expect(shell.state.sidebarOpen).toBe(true)
  })

  it("does not remember a fold the shell performed itself", () => {
    // A phone folds the sidebar on arrival. That is the layout reacting to the
    // room it has, not the reader expressing a preference, so a later session
    // on a wide monitor must open with the sidebar again.
    setViewport(390)
    mount()
    expect(shell.state.sidebarOpen).toBe(false)

    cleanup()
    setViewport(1600)
    mount()

    expect(shell.state.sidebarOpen).toBe(true)
  })

  it("opens at the default width when this browser has said nothing", () => {
    setViewport(1600)
    mount(<Inspector />)
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(chatColumnWidth(shell.state)).toBe(427)
  })

  it("opens with the sidebar out when this browser has said nothing", () => {
    // Without touching the desk: switching it on takes the room from the list
    // deliberately, which is the shell deciding rather than a stored answer.
    setViewport(1600)
    mount()

    expect(shell.state.sidebarOpen).toBe(true)
  })

  it("clamps a remembered width to the viewport it is restored into", () => {
    setViewport(1600)
    mount(<Inspector />)
    act(() => shell.dispatch({ type: "signal-desk", on: true }))
    act(() => shell.dispatch({ type: "resize-chat", width: 900 }))
    act(() => shell.dispatch({ type: "dragging", dragging: false }))

    // The same preference, restored onto a window that cannot hold it. The
    // stored value is left alone — it is legitimate on the wider monitor — and
    // the bound is applied where the room is known.
    cleanup()
    setViewport(1000)
    mount(<Inspector />)
    act(() => shell.dispatch({ type: "signal-desk", on: true }))

    expect(chatColumnWidth(shell.state)).toBeLessThanOrEqual(1000)
  })
})
