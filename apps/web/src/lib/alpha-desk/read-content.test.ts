/**
 * Reading a visual part out of a stored message, and refusing to read one.
 *
 * The reader is total, so every case here is a value rather than a throw. What
 * it is protecting is narrower than it looks: this payload is the only thing in
 * a message that gets handed to a third-party compiler, and a half-read
 * assembly would draw a wrong picture of real evidence. So a payload that is
 * not exactly what this build writes is not repaired — it is dropped, the pane
 * says there is no chart, and the answer beside it is untouched.
 */

import { describe, expect, it } from "vitest"

import { readVisual } from "./read-content"
import { IDLE } from "./live-turn"
import { buildTranscript } from "./transcript"
import type { ThreadMessage } from "./types"

const ASSEMBLY = {
  data: { values: [{ time: "2026-08-24T15:00:00+07:00", close: 71_400 }] },
  chart_spec: {
    chartType: "Line Chart",
    encodings: { x: "time", y: "close" },
    baseSize: { width: 420, height: 300 },
  },
}

function wire(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    version: 1,
    renderer: "flint-echarts",
    flintVersion: "0.5.1",
    asOf: "2026-09-04T17:00:00+07:00",
    title: "FPT · 1D",
    assemblies: [ASSEMBLY],
    evidenceIds: ["ev_1"],
    sourceCallIds: ["call_1"],
    ...overrides,
  }
}

describe("readVisual", () => {
  it("reads the part the backend writes", () => {
    const part = readVisual(wire())

    expect(part?.version).toBe(1)
    expect(part?.assemblies[0].chart_spec.encodings).toEqual({ x: "time", y: "close" })
    expect(part?.assemblies[0].data.values[0].close).toBe(71_400)
    expect(part?.sourceCallIds).toEqual(["call_1"])
  })

  it("keeps the base size the host chose", () => {
    expect(readVisual(wire())?.assemblies[0].chart_spec.baseSize).toEqual({
      width: 420,
      height: 300,
    })
  })

  it("reads a part with no base size", () => {
    const assembly = { ...ASSEMBLY, chart_spec: { ...ASSEMBLY.chart_spec, baseSize: undefined } }

    expect(readVisual(wire({ assemblies: [assembly] }))?.assemblies[0].chart_spec.baseSize)
      .toBeUndefined()
  })

  it("returns null for anything that is not a part", () => {
    expect(readVisual(undefined)).toBeNull()
    expect(readVisual(null)).toBeNull()
    expect(readVisual("chart")).toBeNull()
    expect(readVisual([])).toBeNull()
  })

  it("returns null when the envelope is incomplete", () => {
    expect(readVisual(wire({ version: "1" }))).toBeNull()
    expect(readVisual(wire({ renderer: "" }))).toBeNull()
    expect(readVisual(wire({ flintVersion: "" }))).toBeNull()
    expect(readVisual(wire({ asOf: "" }))).toBeNull()
  })

  it("returns null when nothing names the evidence behind the numbers", () => {
    // The one thing the whole pipeline exists to make impossible. A chart with
    // no provenance is not drawn, whatever else the payload carries.
    expect(readVisual(wire({ evidenceIds: [] }))).toBeNull()
    expect(readVisual(wire({ sourceCallIds: [] }))).toBeNull()
  })

  it("returns null for an assembly that is not one", () => {
    expect(readVisual(wire({ assemblies: [] }))).toBeNull()
    expect(readVisual(wire({ assemblies: "chart" }))).toBeNull()
    expect(readVisual(wire({ assemblies: [{ data: { values: [] } }] }))).toBeNull()
    expect(
      readVisual(
        wire({ assemblies: [{ ...ASSEMBLY, data: { values: ["not a row"] } }] }),
      ),
    ).toBeNull()
  })

  it("returns null when an encoding names something that is not a field", () => {
    const broken = {
      ...ASSEMBLY,
      chart_spec: { ...ASSEMBLY.chart_spec, encodings: { x: "time", y: 3 } },
    }

    expect(readVisual(wire({ assemblies: [broken] }))).toBeNull()
  })
})

describe("the transcript does not know this key exists", () => {
  it("renders an answer that carries a chart exactly as it renders one without", () => {
    // Asserted rather than assumed: the transcript reads the keys it knows, so
    // a sibling part is invisible to it. This is what makes the visual a pane
    // concern and not a second thing the chat column has to agree about.
    const content = {
      text: "FPT đóng cửa ở 71.400 đồng.",
      answer: "FPT đóng cửa ở 71.400 đồng.",
      status: "complete",
    }
    const message = (extra: Record<string, unknown>): ThreadMessage[] => [
      {
        id: 1,
        seq: 1,
        role: "assistant",
        content: { ...content, ...extra },
        created_at: "2026-09-04T10:00:00Z",
      } as unknown as ThreadMessage,
    ]
    const input = { threadId: "t1", live: IDLE, pendingUserText: null }

    expect(
      buildTranscript({ ...input, messages: message({ visual: wire() }) }),
    ).toEqual(buildTranscript({ ...input, messages: message({}) }))
  })
})
