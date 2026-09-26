/**
 * The one place a persisted visual part becomes something ECharts can draw.
 *
 * It exists because **Flint validates nothing**. The contract test in
 * `components/signal-desk/flint-contract.test.ts` proves it against the pinned
 * package: only an unknown `chartType` throws, while a missing required channel
 * comes back as an option with no series and an encoding naming a column no row
 * has comes back as a chart that renders nonsense. Neither of those is a chart
 * a reader should be shown, and neither of them announces itself — so the gate
 * is here, in front of the compiler, and it is the same rule that file proved:
 * every channel the template needs is encoded, and every encoded field is
 * present and finite on every row.
 *
 * The host **prepares input and reads output**. Nothing here rewrites what the
 * package compiled, and nothing persists it: the option is built at render time,
 * lives in memory for as long as the chart is on screen, and is thrown away.
 * A stored option would be a second copy of the truth that could drift from the
 * evidence the part names.
 *
 * Every failure is a value rather than a throw. A visual read out of a message
 * written by an older build, or by a build with a different renderer, is a
 * chart this one cannot draw — and the pane says so while the answer beside it
 * stays perfectly readable.
 */

import { assembleECharts } from "flint-chart/echarts"

import type { VisualPart } from "@/lib/alpha-desk/types"

/** The renderer this module is. A part naming another one is not ours to draw. */
export const RENDERER = "flint-echarts"

/** The payload version this module reads. */
export const VERSION = 1

/**
 * The channels each chart type cannot draw without.
 *
 * Read off the pinned templates rather than guessed: `ecAllTemplateDefs` lists
 * what a template *accepts*, and the required subset is what the contract test
 * pinned. A type absent from this map is one this build will not compile, which
 * is the check that keeps `assembleECharts` from being handed a string a newer
 * backend invented.
 */
const REQUIRED_CHANNELS: Record<string, readonly string[]> = {
  "Candlestick Chart": ["x", "open", "high", "low", "close"],
  "Bar Chart": ["x", "y"],
  "Line Chart": ["x", "y"],
}

/** The height a chart falls back to when its input names none. */
const DEFAULT_HEIGHT = 260

/** What the pane needs to draw one chart: the option, and nothing else. */
export interface CompiledVisual {
  /** The compiled ECharts option, exactly as the package returned it. */
  option: Record<string, unknown>
  /** The chart's own height, so a stacked pair keeps its proportions. */
  height: number
}

export interface CompiledPart {
  title: string
  charts: CompiledVisual[]
}

/**
 * The part as charts, or a reason it is not drawable.
 *
 * `null` and not a thrown error: every caller does the same thing with a
 * failure — draws the pane's own line and leaves the transcript alone — and a
 * throw would make that the responsibility of a boundary rather than of the
 * code that asked.
 */
export function compileVisual(part: VisualPart | null): CompiledPart | null {
  if (part === null) return null
  if (part.version !== VERSION || part.renderer !== RENDERER) return null
  if (part.assemblies.length === 0) return null

  const charts: CompiledVisual[] = []
  for (const assembly of part.assemblies) {
    if (!drawable(assembly)) return null
    let option: Record<string, unknown>
    try {
      // The one call into the package, and the only thing done with its result
      // is to hand it to ECharts. An unknown chart type is the one input it
      // throws on, and `drawable` has already refused every type this build
      // does not know — this catch is for the version that adds a new way.
      option = assembleECharts(assembly) as Record<string, unknown>
    } catch {
      return null
    }
    // The gate above says every encoded field is present, so an option with no
    // series is a template contract that moved under the pin.
    if (!Array.isArray(option.series) || option.series.length === 0) return null
    charts.push({
      option,
      height: assembly.chart_spec.baseSize?.height ?? DEFAULT_HEIGHT,
    })
  }
  return { title: part.title, charts }
}

/**
 * Whether this input draws the chart it claims to, checked before the compiler.
 *
 * The three cases are the three the contract test found, in the order they get
 * worse: a type the templates do not have (throws), a required channel left
 * unencoded (an empty option), and an encoding naming a column no row has (a
 * chart that looks fine and is wrong).
 */
function drawable(assembly: VisualPart["assemblies"][number]): boolean {
  const encodings = assembly.chart_spec.encodings
  const required = REQUIRED_CHANNELS[assembly.chart_spec.chartType]
  if (required === undefined) return false
  if (required.some((channel) => typeof encodings[channel] !== "string")) return false

  const rows = assembly.data.values
  if (rows.length === 0) return false
  const fields = Object.values(encodings)
  return rows.every((row) =>
    fields.every((field) => {
      const value = row[field]
      if (typeof value === "string") return value !== ""
      return typeof value === "number" && Number.isFinite(value)
    }),
  )
}
