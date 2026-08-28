// @vitest-environment jsdom
/**
 * The build state, from the two sides that read it.
 *
 * `buildingLabel` is a pure reading of one live Turn, so most of this is a
 * table of situations rather than a rendered tree: what makes the state correct
 * is *when it stops*, and the two ways it stops — the round drew something, the
 * Turn ended — are both facts about a sequence of events.
 */
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { IDLE, type LiveTurn } from "@/lib/alpha-desk/live-turn"
import type { SignalDeskAnnouncement, ToolCall } from "@/lib/alpha-desk/types"

import { buildingLabel, SignalDeskBuilding } from "./signal-desk-building"

afterEach(cleanup)

function call(overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    id: "call-1",
    name: "run_study",
    status: "running",
    summary: "",
    round: 0,
    error: null,
    result_count: 0,
    results: [],
    ...overrides,
  }
}

function deskView(overrides: Partial<SignalDeskAnnouncement> = {}): SignalDeskAnnouncement {
  return {
    artifactId: "a1",
    studyName: "intraday_liquidity_profile",
    title: "STB",
    blockCount: 3,
    round: 0,
    ...overrides,
  }
}

function turn(overrides: Partial<LiveTurn> = {}): LiveTurn {
  return { ...IDLE, phase: "running", turnId: "t1", ...overrides }
}

describe("what the surface says while a Study runs", () => {
  it("says nothing at all when no drawing tool is in flight", () => {
    expect(buildingLabel(turn())).toBeNull()
    expect(buildingLabel(turn({ toolCalls: [call({ name: "web_search" })] }))).toBeNull()
  })

  it.each(["run_study", "get_series", "render_signal_desk"])(
    "recognises %s as a tool that draws",
    (name) => {
      expect(buildingLabel(turn({ toolCalls: [call({ name })] }))).not.toBeNull()
    },
  )

  it("prefers the sentence the backend wrote for the call", () => {
    // Only the side that made the call knows which Study was chosen.
    const label = buildingLabel(
      turn({ toolCalls: [call({ summary: "Dựng hồ sơ thanh khoản STB" })] }),
    )

    expect(label).toBe("Dựng hồ sơ thanh khoản STB")
  })

  it("falls back to a generic line rather than an empty one", () => {
    expect(buildingLabel(turn({ toolCalls: [call({ summary: "  " })] }))).toBe(
      "Đang dựng deskView",
    )
  })

  it("clears as soon as the round it belongs to has drawn something", () => {
    // The desk view and the call's outcome arrive on the same stream and the order
    // between them is the backend's business, so the round is what they share.
    const state = turn({
      toolCalls: [call({ round: 2 })],
      deskViews: [deskView({ round: 2 })],
    })

    expect(buildingLabel(state)).toBeNull()
  })

  it("keeps saying so while a second round is still building", () => {
    const state = turn({
      toolCalls: [call({ id: "c1", round: 1 }), call({ id: "c2", round: 2 })],
      deskViews: [deskView({ round: 1 })],
    })

    expect(buildingLabel(state)).not.toBeNull()
  })

  it.each(["completed", "failed", "cancelled", "incomplete"] as const)(
    "leaves nothing spinning after a Turn that %s",
    (phase) => {
      // A Turn that produced nothing must not leave the pane building forever.
      expect(buildingLabel(turn({ phase, toolCalls: [call()] }))).toBeNull()
    },
  )
})

describe("the shape held while the numbers arrive", () => {
  it("announces what is being built and nothing else", () => {
    render(<SignalDeskBuilding label="Dựng hồ sơ thanh khoản STB" />)

    expect(screen.getByText("Dựng hồ sơ thanh khoản STB")).toBeInTheDocument()
  })
})
