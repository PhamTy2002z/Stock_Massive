/**
 * The chart chrome every recharts widget shares, so none of them invents it.
 *
 * All of it is CSS variables rather than literals. The app opens in dark and
 * the reader can switch to light, and a chart whose axis is `#888` is legible
 * in one of those — the tokens are defined for both, so the same declaration
 * reads correctly in either.
 *
 * Nothing here is a *palette*: which series gets which colour is the widget's
 * decision, because it is a decision about meaning. What is shared is the grid,
 * the axis and the tooltip — the parts a reader should never notice changing
 * from one block to the next.
 */

export const AXIS = {
  stroke: "hsl(var(--border))",
  tick: { fill: "hsl(var(--ink-5))", fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const

export const GRID = {
  stroke: "hsl(var(--hairline))",
  strokeDasharray: "2 4",
  vertical: false,
} as const

export const TOOLTIP_STYLE = {
  cursor: { fill: "hsl(var(--surface-sunken))" },
  contentStyle: {
    background: "hsl(var(--surface-menu))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "0.5rem",
    fontSize: "0.75rem",
    color: "hsl(var(--ink-1))",
  },
  labelStyle: { color: "hsl(var(--ink-4))" },
  itemStyle: { color: "hsl(var(--ink-1))" },
} as const
