/**
 * The host's gate in front of a library that has none.
 *
 * `components/signal-desk/flint-contract.test.ts` proved what the pinned
 * package does with a bad input: it draws it. So the assertions here are all
 * one shape — the payloads that would have produced a wrong chart come back as
 * `null` instead, and the pane draws its own line rather than a picture nobody
 * can source.
 *
 * The fixture is the one the backend assembles, written out rather than
 * imported, because this file is the boundary's browser half: if the two ever
 * disagree about a field name, that disagreement has to be visible as a failing
 * test and not absorbed by a shared constant.
 */

import { describe, expect, it } from "vitest"

import type { VisualPart } from "@/lib/alpha-desk/types"

import { compileVisual } from "./compile-visual"

/** Prices in whole dong and bar closes in ICT, as `agent/visual.py` writes them. */
const ROWS = [
  {
    time: "2026-08-24T15:00:00+07:00",
    open: 72_500,
    high: 72_700,
    low: 71_400,
    close: 71_400,
    volume: 4_611_900,
  },
  {
    time: "2026-08-25T15:00:00+07:00",
    open: 72_500,
    high: 72_700,
    low: 71_400,
    close: 71_400,
    volume: 4_611_900,
  },
]

function part(overrides: Partial<VisualPart> = {}): VisualPart {
  return {
    version: 1,
    renderer: "flint-echarts",
    flintVersion: "0.5.1",
    asOf: "2026-09-04T17:00:00+07:00",
    title: "FPT · 1D · 2026-08-24 → 2026-08-25",
    assemblies: [
      {
        data: { values: ROWS },
        chart_spec: {
          chartType: "Candlestick Chart",
          encodings: {
            x: "time",
            open: "open",
            high: "high",
            low: "low",
            close: "close",
          },
          baseSize: { width: 420, height: 260 },
        },
      },
      {
        data: { values: ROWS },
        chart_spec: {
          chartType: "Bar Chart",
          encodings: { x: "time", y: "volume" },
          baseSize: { width: 420, height: 110 },
        },
      },
    ],
    evidenceIds: ["ev_1"],
    sourceCallIds: ["call_1"],
    ...overrides,
  }
}

describe("what the pane can draw", () => {
  it("compiles the stacked pair the backend assembles", () => {
    const compiled = compileVisual(part())

    expect(compiled?.charts).toHaveLength(2)
    expect(compiled?.title).toBe("FPT · 1D · 2026-08-24 → 2026-08-25")
    expect(compiled?.charts.map((chart) => chart.height)).toEqual([260, 110])
  })

  it("hands back the package's own option, unedited", () => {
    const compiled = compileVisual(part())

    const series = compiled?.charts[0].option.series as { type: string }[]
    expect(series.map((item) => item.type)).toEqual(["candlestick"])
    // Every row survives. A silently truncated series would be a wrong chart
    // rather than a missing one.
    expect(compiled?.charts[0].option._dataLength).toBe(ROWS.length)
  })

  it("compiles a multi-series line", () => {
    const compiled = compileVisual(
      part({
        assemblies: [
          {
            data: {
              values: [
                { time: "2026-08-24T15:00:00+07:00", close: 71_400, symbol: "FPT" },
                { time: "2026-08-24T15:00:00+07:00", close: 25_000, symbol: "VNM" },
              ],
            },
            chart_spec: {
              chartType: "Line Chart",
              encodings: { x: "time", y: "close", color: "symbol" },
              baseSize: { width: 420, height: 300 },
            },
          },
        ],
      }),
    )

    const series = compiled?.charts[0].option.series as { name: string }[]
    expect(series.map((item) => item.name)).toEqual(["FPT", "VNM"])
  })
})

describe("what the pane refuses", () => {
  it("refuses a part from a build it does not know", () => {
    expect(compileVisual(part({ version: 2 }))).toBeNull()
    expect(compileVisual(part({ renderer: "vega" }))).toBeNull()
  })

  it("refuses nothing at all", () => {
    expect(compileVisual(null)).toBeNull()
    expect(compileVisual(part({ assemblies: [] }))).toBeNull()
  })

  it("refuses a chart type this build cannot draw", () => {
    // Flint throws on this one, which is the only input it does refuse. The
    // refusal still has to be a value rather than an exception in the pane.
    const broken = part()
    broken.assemblies[0].chart_spec.chartType = "Ichimoku Cloud"

    expect(compileVisual(broken)).toBeNull()
  })

  it("refuses a required channel left unencoded", () => {
    // Flint answers this with an option that has no series at all — a chart
    // that renders as an empty box.
    const broken = part()
    delete broken.assemblies[0].chart_spec.encodings.close

    expect(compileVisual(broken)).toBeNull()
  })

  it("refuses an encoding naming a column no row has", () => {
    // The worst of the three, because it looks like it worked: a candlestick
    // series comes back and nothing in the option says the field was never there.
    const broken = part()
    broken.assemblies[0].chart_spec.encodings.close = "closing_price"

    expect(compileVisual(broken)).toBeNull()
  })

  it("refuses a row whose price is not a number", () => {
    const broken = part()
    broken.assemblies[0].data.values = [{ ...ROWS[0], close: null }]

    expect(compileVisual(broken)).toBeNull()
  })

  it("refuses an empty dataset", () => {
    const broken = part()
    broken.assemblies[0].data.values = []

    expect(compileVisual(broken)).toBeNull()
  })

  it("refuses the whole part when only its second chart is broken", () => {
    // Half a stacked pair is a price chart with the volume silently missing,
    // which reads as a chart of everything there was.
    const broken = part()
    delete broken.assemblies[1].chart_spec.encodings.y

    expect(compileVisual(broken)).toBeNull()
  })
})

describe("nothing compiled is kept", () => {
  it("builds a fresh option on every call", () => {
    const input = part()

    const first = compileVisual(input)
    const second = compileVisual(input)

    expect(first?.charts[0].option).not.toBe(second?.charts[0].option)
    // Deterministic all the same: the same input is the same chart, which is
    // what makes a refresh free rather than a re-run.
    expect(JSON.stringify(first)).toBe(JSON.stringify(second))
  })

  it("leaves the input exactly as it found it", () => {
    const input = part()
    const before = JSON.stringify(input)

    compileVisual(input)

    expect(JSON.stringify(input)).toBe(before)
  })
})
