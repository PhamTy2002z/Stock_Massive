// Shared Recharts theming constants.

/** Props for <CartesianGrid {...CHART_GRID_PROPS} /> */
export const CHART_GRID_PROPS = {
  strokeDasharray: "3 3",
  stroke: "hsl(var(--border))",
} as const

/** Style for <Tooltip contentStyle={CHART_TOOLTIP_STYLE} /> */
export const CHART_TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
} as const
