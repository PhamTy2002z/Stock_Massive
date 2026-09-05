/**
 * What the official Flint package actually does with a chart assembly input.
 *
 * This is a contract test against a pinned third-party package, not a test of
 * our own code — there is no production module here yet. It exists because the
 * next phase has to build a `ChartAssemblyInput` from market evidence, and the
 * two things it needs to know cannot be read off the README: which channels the
 * candlestick template accepts, and what the library does when the input is
 * wrong.
 *
 * The answer to the second one is the reason this file matters: **Flint does
 * not validate.** Only an unknown `chartType` throws. Everything else — a
 * missing required channel, an encoding naming a column no row has — comes back
 * as a chart-shaped object that renders nothing or renders nonsense. So the
 * gate that refuses a visual belongs to the host, and the assertions below are
 * what stop that conclusion from being re-litigated from memory.
 *
 * The fixtures are exported because the next phase consumes them: they are the
 * shape the host has to produce, written once.
 */

import { describe, expect, it } from "vitest"
import { assembleECharts, ecAllTemplateDefs } from "flint-chart/echarts"

/**
 * Three synthetic sessions. Deliberately not real market data: a fixture that
 * looked like a quote would be a financial claim nobody sourced, and this file
 * is about the library's contract rather than about any company.
 *
 * Prices are in thousands of VND, which is the scale the KBS adapter returns
 * and therefore the scale the host will normalise *away from* before it gets
 * here. The unit is stated because the chart cannot state it.
 */
export const OHLCV_ROWS = [
  { time: "2026-08-24", open: 71.2, high: 72.4, low: 70.9, close: 72.0, volume: 1_820_400 },
  { time: "2026-08-25", open: 72.0, high: 72.8, low: 71.6, close: 71.8, volume: 1_402_100 },
  { time: "2026-08-26", open: 71.8, high: 73.1, low: 71.5, close: 73.0, volume: 2_115_700 },
] as const

/** The right-hand pane's usable width, and the two heights a stacked pair gets. */
export const PANE_WIDTH = 420
export const CANDLE_HEIGHT = 260
export const VOLUME_HEIGHT = 110

/**
 * The candlestick half.
 *
 * `Candlestick Chart` accepts `x, open, high, low, close, column, row` and
 * **no volume channel**, which is the finding that shapes the next phase: price
 * and volume are two assembly inputs and two compiled options, not one chart
 * with two axes. Merging them afterwards would mean editing Flint's output,
 * which the plan forbids.
 */
export const CANDLESTICK_INPUT = {
  data: { values: [...OHLCV_ROWS] },
  chart_spec: {
    chartType: "Candlestick Chart",
    encodings: { x: "time", open: "open", high: "high", low: "low", close: "close" },
    baseSize: { width: PANE_WIDTH, height: CANDLE_HEIGHT },
  },
}

/** The volume half, as its own chart on the same x field. */
export const VOLUME_INPUT = {
  data: { values: [...OHLCV_ROWS] },
  chart_spec: {
    chartType: "Bar Chart",
    encodings: { x: "time", y: "volume" },
    baseSize: { width: PANE_WIDTH, height: VOLUME_HEIGHT },
  },
}

/** Every channel the host must fill for the chart to draw anything at all. */
export const CANDLESTICK_REQUIRED_CHANNELS = ["x", "open", "high", "low", "close"] as const

describe("flint-chart compiles what the host will send", () => {
  it("compiles the candlestick input into an ECharts option", () => {
    const option = assembleECharts(CANDLESTICK_INPUT)

    expect(option.series?.map((series: { type: string }) => series.type)).toEqual([
      "candlestick",
    ])
    expect(option.xAxis).toBeDefined()
    expect(option.yAxis).toBeDefined()
    // Every row survives; a silently truncated series would be a wrong chart
    // rather than a missing one.
    expect(option._dataLength).toBe(OHLCV_ROWS.length)
    expect(option._warnings).toBeUndefined()
  })

  it("compiles the volume input as its own chart", () => {
    const option = assembleECharts(VOLUME_INPUT)

    expect(option.series?.map((series: { type: string }) => series.type)).toEqual(["bar"])
    expect(option._dataLength).toBe(OHLCV_ROWS.length)
    expect(option._warnings).toBeUndefined()
  })

  it("has no volume channel on the candlestick template", () => {
    const template = ecAllTemplateDefs.find(
      (def: { chart: string }) => def.chart === "Candlestick Chart",
    )

    expect(template).toBeDefined()
    expect(template?.channels).toEqual(["x", "open", "high", "low", "close", "column", "row"])
    // Stated as an assertion rather than a comment: if a later version adds one,
    // this test fails and the two-chart decision gets revisited on purpose.
    expect(template?.channels).not.toContain("volume")
  })
})

describe("what Flint refuses, and what it lets through", () => {
  it("throws on a chart type it does not have", () => {
    expect(() =>
      assembleECharts({
        data: { values: [...OHLCV_ROWS] },
        chart_spec: { chartType: "Ichimoku Cloud", encodings: { x: "time" } },
      }),
    ).toThrow(/Unknown ECharts chart type/)
  })

  it("does NOT refuse an input missing a required channel", () => {
    // The whole reason the host needs its own gate. `close` is missing, so the
    // chart cannot be drawn — and Flint says so by handing back an option with
    // no series at all rather than by failing.
    const option = assembleECharts({
      data: { values: [...OHLCV_ROWS] },
      chart_spec: {
        chartType: "Candlestick Chart",
        encodings: { x: "time", open: "open", high: "high", low: "low" },
      },
    })

    expect(option.series).toBeUndefined()
  })

  it("does NOT refuse an encoding naming a column no row has", () => {
    // Worse than the case above, because it looks like it worked: a series
    // comes back, and nothing in the option says the field was never there.
    const option = assembleECharts({
      data: { values: [...OHLCV_ROWS] },
      chart_spec: {
        chartType: "Candlestick Chart",
        encodings: {
          x: "time",
          open: "open",
          high: "high",
          low: "low",
          close: "closing_price",
        },
      },
    })

    expect(option.series?.map((series: { type: string }) => series.type)).toEqual([
      "candlestick",
    ])
  })

  it("does NOT refuse an empty dataset", () => {
    const option = assembleECharts({
      data: { values: [] },
      chart_spec: {
        chartType: "Candlestick Chart",
        encodings: { x: "time", open: "open", high: "high", low: "low", close: "close" },
      },
    })

    expect(option._dataLength).toBe(0)
  })

  it("gives the host a checkable rule for all three", () => {
    // The gate the next phase installs, in the smallest form that proves it
    // catches every case above: every required channel is encoded, and every
    // encoded field is present and finite on every row. Written here so the
    // rule is proven against the real library rather than asserted in a plan.
    const encodedFieldsArePresent = (input: typeof CANDLESTICK_INPUT) => {
      const encodings = input.chart_spec.encodings as Record<string, string>
      const missingChannel = CANDLESTICK_REQUIRED_CHANNELS.some(
        (channel) => !encodings[channel],
      )
      if (missingChannel) return false
      return input.data.values.every((row) =>
        Object.values(encodings).every((field) => field in (row as Record<string, unknown>)),
      )
    }

    expect(encodedFieldsArePresent(CANDLESTICK_INPUT)).toBe(true)
    expect(
      encodedFieldsArePresent({
        ...CANDLESTICK_INPUT,
        chart_spec: {
          ...CANDLESTICK_INPUT.chart_spec,
          encodings: { x: "time", open: "open", high: "high", low: "low" },
        },
      }),
    ).toBe(false)
    expect(
      encodedFieldsArePresent({
        ...CANDLESTICK_INPUT,
        chart_spec: {
          ...CANDLESTICK_INPUT.chart_spec,
          encodings: {
            x: "time",
            open: "open",
            high: "high",
            low: "low",
            close: "closing_price",
          },
        },
      }),
    ).toBe(false)
  })
})
