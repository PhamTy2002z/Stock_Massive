/**
 * The chart chrome and the chart palette every recharts widget shares.
 *
 * All of it is CSS variables rather than literals. The app opens in dark and
 * the reader can switch to light, and a chart whose axis is `#888` is legible
 * in one of those — the tokens are defined for both, so the same declaration
 * reads correctly in either.
 *
 * **The palette is shared, and that is the point.** It used to be each widget's
 * own decision, and every one of them reached into the app's chart ramp, whose
 * lead entry is the brand's Ignition Amber byte for byte and whose third is
 * Ceiling Violet. A whole series painted in the amber reads as a control, and a
 * ranking painted in the violet reads as *trần* to a Vietnamese reader — both
 * are the chart borrowing a meaning nothing measured. So the neutral series
 * colour lives here, once, and the widgets no longer choose it.
 *
 * **`FOCUS` is a single element, never a series.** The peak bucket, the ranked
 * leader, the current price marker: the one row a reader came for. A second
 * amber thing on the same chart spends the only mark that means "this one".
 */

/** The one categorical series colour: neither the amber nor the market pair. */
export const SERIES = "hsl(var(--widget-series))"

/** A companion series, told apart by weight rather than by a second hue. */
export const SERIES_MUTED = "hsl(var(--widget-neutral))"

/** The one element the answer is actually about. Never a whole series. */
export const FOCUS = "hsl(var(--widget-focus))"

/** The ground a bar or a rule is drawn against. */
export const TRACK = "hsl(var(--widget-track))"

export const AXIS = {
  stroke: "hsl(var(--widget-axis))",
  tick: {
    fill: "hsl(var(--widget-axis))",
    fontFamily: "var(--font-jetbrains-mono), ui-monospace, monospace",
    fontFeatureSettings: '"tnum" 1',
    fontSize: 11,
    fontWeight: 500,
  },
  tickLine: false,
  axisLine: false,
} as const

export const GRID = {
  stroke: "hsl(var(--widget-grid))",
  strokeDasharray: "2 4",
  vertical: false,
} as const

export const TOOLTIP_STYLE = {
  cursor: { fill: "hsl(var(--widget-track) / 0.45)" },
  contentStyle: {
    background: "hsl(var(--widget-surface))",
    border: "1px solid hsl(var(--widget-grid))",
    borderRadius: "0.5rem",
    fontSize: "0.75rem",
    fontVariantNumeric: "tabular-nums",
    color: "hsl(var(--widget-ink))",
  },
  labelStyle: { color: "hsl(var(--widget-ink-muted))" },
  itemStyle: { color: "hsl(var(--widget-ink))" },
} as const
