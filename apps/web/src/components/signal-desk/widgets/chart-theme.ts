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
 * {@link resolveRoles} is where that is enforced rather than trusted.
 *
 * **What a colour means is the engine's to say, and the theme's to draw.** A
 * frame may declare what its series and its points *are* — the one the answer is
 * about, a quarter that fell, the third of four groups — and {@link colorFor}
 * turns that into the token this theme paints it with. The engine never names a
 * colour; a name it chose would be legible in one of the two themes.
 */

/** The default series colour: neither the amber nor the market pair. */
export const SERIES = "hsl(var(--widget-series))"

/** A companion series, told apart by weight rather than by a second hue. */
export const SERIES_MUTED = "hsl(var(--widget-neutral))"

/** The one element the answer is actually about. Never a whole series. */
export const FOCUS = "hsl(var(--widget-focus))"

/**
 * Every meaning a frame may declare, and the token this theme draws it with.
 *
 * Closed on purpose, and matched to the server's own list
 * (`studies/contracts.py`): a word that is not here is a claim this build cannot
 * draw, and drawing it as the default series colour is the honest answer —
 * silently inventing a hue for it would be the browser deciding what a number
 * means.
 */
const ROLE_TOKENS: Record<string, string> = {
  series: "--widget-series",
  muted: "--widget-series-muted",
  focus: "--widget-focus",
  up: "--widget-up",
  down: "--widget-down",
  neutral: "--widget-neutral",
  "category:1": "--widget-cat-1",
  "category:2": "--widget-cat-2",
  "category:3": "--widget-cat-3",
  "category:4": "--widget-cat-4",
  "category:5": "--widget-cat-5",
  "category:6": "--widget-cat-6",
  // The comparison pair, and it is not the market pair wearing another name. A
  // number that *rose* and a number that is *better than the one beside it* are
  // different claims — VIC's drawdown falling is `down` and also `winner` — so a
  // chart that had to choose between them would drop one of the two things the
  // picture is about.
  winner: "--widget-up",
  loser: "--widget-down",
  // What something is being compared *against*: an index, a sector median. Told
  // apart from the subject by weight rather than by a hue of its own, because a
  // reference line competing for attention with the line it references is a
  // chart with two subjects.
  benchmark: "--widget-benchmark",
  // A cell a reader should not read past without the caveat beside it.
  warning: "--widget-warning",
  // Real, and older than the rest of the picture. The one condition a frame can
  // carry that no refusal covers: it has a value, and the value is from another
  // day.
  stale: "--widget-neutral",
}

/** The colour for one declared meaning, or the default series colour. */
export function colorFor(role: unknown): string {
  const token = typeof role === "string" ? ROLE_TOKENS[role] : undefined
  return token === undefined ? SERIES : `hsl(var(${token}))`
}

export interface ResolvedRoles {
  /** One entry per element handed in, in the same order. */
  roles: (string | null)[]
  /** True when more than one element claimed the focus and none now has it. */
  focusSpent: boolean
}

/**
 * The declared meanings, with the focus mark spent at most once.
 *
 * The focus is the only role that is a claim about the *picture* rather than
 * about one number: it says "this is the one". Two of them say nothing, and a
 * chart with half its bars in amber reads as a chart about amber. So a frame
 * that marks two has both marks withdrawn — nothing is highlighted rather than
 * everything, because the numbers are still right and only the emphasis was
 * wrong. Every other role in the same frame is left exactly as it was.
 *
 * Withdrawn to `null` rather than to a colour, so each widget falls back to
 * whatever *it* draws an unclaimed element in: the series colour on a chart, the
 * page's own ink on a tile.
 *
 * Silent to the reader by design. The chart still says what it measured, the
 * table under it carries the same numbers, and "two peaks were marked" is a
 * sentence about how this system is built, not about the company.
 */
export function resolveRoles(
  declared: readonly (string | null | undefined)[],
): ResolvedRoles {
  const roles = declared.map((role) => (typeof role === "string" ? role : null))
  const focused = roles.filter((role) => role === "focus").length
  if (focused <= 1) return { roles, focusSpent: false }

  return {
    roles: roles.map((role) => (role === "focus" ? null : role)),
    focusSpent: true,
  }
}

/**
 * The colour for one cell's declared meaning, or nothing.
 *
 * `null` rather than the series colour, unlike {@link colorFor}: a table cell
 * that claims nothing keeps the page's own ink, and painting it the chart's
 * neutral would make every cell of every comparison look claimed.
 */
export function cellColorFor(role: unknown): string | null {
  const token = typeof role === "string" ? ROLE_TOKENS[role] : undefined
  return token === undefined ? null : `hsl(var(${token}))`
}

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
