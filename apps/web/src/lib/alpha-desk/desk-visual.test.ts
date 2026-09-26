/**
 * Which chart the pane is about, and — mostly — which chart it is *not* about.
 *
 * Every case here is an ownership question. The one that matters most is the
 * running Turn: the previous answer's chart is still in the transcript and
 * still true about the question it answered, and leaving it on screen under a
 * new question would make it read as the answer to that one instead.
 */

import { describe, expect, it } from "vitest"

import { selectDeskView } from "./desk-visual"
import { IDLE, type LiveTurn } from "./live-turn"
import type { ThreadMessage } from "./types"

const VISUAL = {
  version: 1,
  renderer: "flint-echarts",
  flintVersion: "0.5.1",
  asOf: "2026-09-04T17:00:00+07:00",
  title: "FPT · 1D",
  assemblies: [
    {
      data: { values: [{ time: "2026-08-24T15:00:00+07:00", close: 71_400 }] },
      chart_spec: {
        chartType: "Line Chart",
        encodings: { x: "time", y: "close" },
        baseSize: { width: 420, height: 300 },
      },
    },
  ],
  evidenceIds: ["ev_1"],
  sourceCallIds: ["call_1"],
}

function message(
  role: ThreadMessage["role"],
  seq: number,
  content: Record<string, unknown> = {},
): ThreadMessage {
  return {
    id: seq,
    seq,
    role,
    content: { text: "…", ...content },
    created_at: "2026-09-04T10:00:00Z",
  } as unknown as ThreadMessage
}

function running(threadId: string | null = "t1"): LiveTurn {
  return { ...IDLE, phase: "running", threadId, turnId: "turn-1" }
}

describe("selectDeskView", () => {
  it("is empty before the conversation has any answer", () => {
    expect(selectDeskView([], IDLE, "t1")).toEqual({ state: "empty" })
    expect(selectDeskView([message("user", 1)], IDLE, "t1")).toEqual({ state: "empty" })
  })

  it("shows the chart of the settled answer", () => {
    const view = selectDeskView(
      [message("user", 1), message("assistant", 2, { visual: VISUAL })],
      IDLE,
      "t1",
    )

    expect(view.state).toBe("chart")
    expect(view.state === "chart" && view.visual.title).toBe("FPT · 1D")
  })

  it("says there is no chart when the answer settled without one", () => {
    expect(
      selectDeskView([message("assistant", 2)], IDLE, "t1"),
    ).toEqual({ state: "none" })
  })

  it("takes the latest answer, not the last one that had a chart", () => {
    const view = selectDeskView(
      [message("assistant", 1, { visual: VISUAL }), message("assistant", 3)],
      IDLE,
      "t1",
    )

    // The chart above answered a question two Turns ago. Keeping it because the
    // newer answer has none would attach it to the wrong question.
    expect(view).toEqual({ state: "none" })
  })

  it("drops the old chart the moment a new Turn starts", () => {
    const view = selectDeskView(
      [message("assistant", 2, { visual: VISUAL })],
      running(),
      "t1",
    )

    expect(view).toEqual({ state: "working" })
  })

  it("ignores a Turn running in another Thread", () => {
    const view = selectDeskView(
      [message("assistant", 2, { visual: VISUAL })],
      running("t2"),
      "t1",
    )

    expect(view.state).toBe("chart")
  })

  it("shows nothing but this Thread's own messages", () => {
    // The scope is the argument: the selector is handed the open Thread's
    // messages, so there is no cache for another conversation's chart to be in.
    expect(selectDeskView([], running(), "t1")).toEqual({ state: "working" })
  })

  it("refuses a persisted chart it cannot read", () => {
    const view = selectDeskView(
      [message("assistant", 2, { visual: { version: 1, renderer: "flint-echarts" } })],
      IDLE,
      "t1",
    )

    expect(view).toEqual({ state: "none" })
  })

  it("is settled again as soon as the Turn ends", () => {
    const settled: LiveTurn = { ...IDLE, phase: "completed", threadId: "t1" }

    expect(
      selectDeskView([message("assistant", 2, { visual: VISUAL })], settled, "t1").state,
    ).toBe("chart")
  })
})
