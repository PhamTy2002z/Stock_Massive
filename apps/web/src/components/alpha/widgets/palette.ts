/**
 * The Widget registry's palette, as the components reference it.
 *
 * The colour *values* live in one place — the `--widget-*` block at the end of
 * `globals.css` — and this module is the only route to them. Nothing under
 * `widgets/` writes a colour of its own, so "the palette is defined in one
 * place" is a property of the import graph rather than a convention.
 *
 * The registry does not inherit `chart-theme.ts` or the `--chart-*` scale, and
 * that is deliberate (ADR-0012): the existing charts carry two measured
 * defects — series painted pure white, and `--stock-up` / `--stock-down`
 * referenced without ever being defined — and a shared layer would have carried
 * both in here.
 *
 * **Colour never carries meaning alone.** Every direction below also has a
 * `sign` and a Vietnamese word, and every Widget states its reading in a
 * textual summary and again in its data table. A reader who cannot separate
 * the hues loses decoration and no information.
 */

export const WIDGET_PALETTE = {
  surface: "hsl(var(--widget-surface))",
  ink: "hsl(var(--widget-ink))",
  inkMuted: "hsl(var(--widget-ink-muted))",
  series: "hsl(var(--widget-series))",
  seriesMuted: "hsl(var(--widget-series-muted))",
  up: "hsl(var(--widget-up))",
  down: "hsl(var(--widget-down))",
  neutral: "hsl(var(--widget-neutral))",
  track: "hsl(var(--widget-track))",
  grid: "hsl(var(--widget-grid))",
  axis: "hsl(var(--widget-axis))",
  focus: "hsl(var(--widget-focus))",
} as const

export type WidgetPaletteToken = keyof typeof WIDGET_PALETTE

export type Direction = "up" | "down" | "flat"

/** Which way a value points, once, so no component decides it twice. */
export function directionOf(value: number | null | undefined): Direction {
  if (value === null || value === undefined || Number.isNaN(value)) return "flat"
  if (value > 0) return "up"
  if (value < 0) return "down"
  return "flat"
}

export function directionColor(direction: Direction): string {
  if (direction === "up") return WIDGET_PALETTE.up
  if (direction === "down") return WIDGET_PALETTE.down
  return WIDGET_PALETTE.neutral
}

/**
 * The non-colour half of the same encoding.
 *
 * Rendered beside every coloured mark that means a direction, so the direction
 * survives greyscale, a colour-vision deficiency, and a printed page.
 */
export function directionSign(direction: Direction): string {
  if (direction === "up") return "▲"
  if (direction === "down") return "▼"
  return "•"
}

export function directionLabel(direction: Direction): string {
  if (direction === "up") return "tăng"
  if (direction === "down") return "giảm"
  return "không đổi"
}
