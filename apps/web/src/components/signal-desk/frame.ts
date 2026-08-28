/**
 * Reading a frame, once, so five widgets do not each read it differently.
 *
 * A frame is positional: `rows` are arrays lined up against `columns`, because
 * a heatmap is mostly cells and objects would repeat every column name once per
 * session. That saves bytes on the wire and costs a lookup here, and the lookup
 * is the thing worth writing down — five components each doing
 * `columns.indexOf(...)` is five places a renamed column fails differently.
 *
 * Every reader is total. A column that is not there, a cell holding a string
 * where a number belongs, a row shorter than its header: all of them answer
 * `null`, and `null` is drawn as "no data" rather than as zero. That
 * distinction is the whole point — a bucket with no bar because nothing traded
 * and a bucket with no bar because the exchange has no such bucket are
 * different claims, and only one of them is a fact about the company.
 */

import type { Frame } from "@/lib/alpha-desk/types"

/** Where one column sits, or `-1`. */
export function columnIndex(frame: Frame, column: unknown): number {
  return typeof column === "string" ? frame.columns.indexOf(column) : -1
}

/** The Vietnamese a person reads for one column, or the column's own name. */
export function labelOf(frame: Frame, column: string): string {
  return frame.labels[column] ?? column
}

/** One cell as a number, or `null` when it is absent or not one. */
export function numberAt(row: unknown[], index: number): number | null {
  if (index < 0 || index >= row.length) return null
  const value = row[index]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

/** One cell as text a person can read, or an em dash for nothing. */
export function textAt(row: unknown[], index: number): string {
  if (index < 0 || index >= row.length) return "—"
  const value = row[index]
  if (typeof value === "string") return value
  if (typeof value === "number" && Number.isFinite(value)) return formatNumber(value)
  return "—"
}

/**
 * How large a number is, and the two ways of saying so.
 *
 * `word` belongs beside a financial unit. Axis ticks use the same scale but
 * state the word once above the plot, so a narrow y-axis never has to wrap
 * "nghìn đồng" or "tỷ đồng" under every number.
 */
interface Magnitude {
  scaled: number
  divisor: number
  word: string
}

function magnitudeOf(value: number): Magnitude {
  const size = Math.abs(value)
  if (size >= 1e9) return { scaled: value / 1e9, divisor: 1e9, word: "tỷ" }
  if (size >= 1e6) return { scaled: value / 1e6, divisor: 1e6, word: "triệu" }
  if (size >= 1e4) return { scaled: value / 1e3, divisor: 1e3, word: "nghìn" }
  return { scaled: value, divisor: 1, word: "" }
}

/**
 * A number at a width a reader can take in at a glance.
 *
 * Vietnamese grouping with at most one decision-useful decimal. Below ten
 * thousand nothing is abbreviated — the digits are already readable.
 */
export function formatNumber(value: number): string {
  const { scaled, word } = magnitudeOf(value)
  return joinMeasure(decimal(scaled), word)
}

/**
 * The same number where a unit follows it, with the magnitude spelt out.
 *
 * **One layer owns magnitude, and it is this one.** A frame carries the number
 * and the unit in separate cells, so a tile prints two things side by side; the
 * abbreviation that reads cleanly alone on an axis reads as a second unit when
 * something follows it. The word does not.
 */
export function formatQuantity(value: number): string {
  return formatNumber(value)
}

/**
 * Units a Study names in its source's vocabulary, said the way a reader reads.
 *
 * A Study counts what its provider counts, and one provider counts in English.
 * What reaches a reader is narration and narration is Vietnamese, so the frame
 * keeps `shares` — it is the number's own unit and the table is the record —
 * and the surface says `cp`. Currency names are normalized to `đồng`; anything
 * not listed is passed through unchanged.
 */
const UNIT_WORDS: Record<string, string> = {
  vnd: "đồng",
  "đ": "đồng",
  đồng: "đồng",
  share: "cp",
  shares: "cp",
}

export function formatUnit(unit: string): string {
  return UNIT_WORDS[unit.toLowerCase()] ?? unit
}

export interface MeasureParts {
  /** The comparable figure, without a suffix. */
  value: string
  /** Magnitude and measurement, kept together so they cannot wrap apart. */
  unit: string
}

/** One financial figure split into the two typographic roles a surface needs. */
export function formatMeasureParts(value: number, unit: unknown): MeasureParts {
  const suffix = typeof unit === "string" ? formatUnit(unit.trim()) : ""
  if (suffix === "%") return { value: decimal(value), unit: "%" }

  const { scaled, word } = magnitudeOf(value)
  return {
    value: decimal(scaled),
    unit: [word, suffix].filter(Boolean).join(" "),
  }
}

/**
 * One measurement as a single phrase: the number, its magnitude, and its unit.
 *
 * A percentage closes up against its sign because that is how a percentage is
 * written; everything else is separated by a space.
 */
export function formatMeasure(value: number, unit: unknown): string {
  const parts = formatMeasureParts(value, unit)
  return parts.unit === "%"
    ? `${parts.value}%`
    : joinMeasure(parts.value, parts.unit)
}

/** A percentage already stored in percentage points. */
export function formatPercentPoint(value: number): string {
  return `${decimal(value)}%`
}

/** A share of a whole, as the percentage a reader expects. */
export function formatPercent(value: number): string {
  return formatPercentPoint(value * 100)
}

/**
 * One value formatted the way the block's options asked for.
 *
 * The server chooses the format because it chose what the column means: a share
 * stored as `0.1938` is a percentage and stored as `19.38` is already one, and
 * only the layer that computed it knows which.
 */
export function formatValue(value: number, format: unknown): string {
  return format === "percent" ? formatPercent(value) : formatNumber(value)
}

export interface AxisPresentation {
  /** One persistent label above the plot, never repeated in tick text. */
  unit: string
  /** A short number for a tick. */
  format: (value: number) => string
  /** The complete measurement for a tooltip or accessible description. */
  measure: (value: number) => string
}

/**
 * One common scale for a chart or numeric table column.
 *
 * A common scale keeps comparable values aligned: a profit column does not
 * switch between "950 triệu" and "1,2 tỷ" halfway down the table. The unit is
 * stated once in the header and tick labels remain numbers only.
 */
export function axisPresentation(
  values: number[],
  unit: unknown,
  format?: unknown,
): AxisPresentation {
  if (format === "percent") {
    return presentation(100, "%", (value) => value * 100)
  }

  const suffix = typeof unit === "string" ? formatUnit(unit.trim()) : ""
  if (suffix === "%") return presentation(1, "%")

  const largest = Math.max(0, ...values.map((value) => Math.abs(value)))
  const { divisor, word } = magnitudeOf(largest)
  return presentation(divisor, [word, suffix].filter(Boolean).join(" "))
}

function presentation(
  divisor: number,
  unit: string,
  transform: (value: number) => number = (value) => value / divisor,
): AxisPresentation {
  const format = (value: number) => decimal(transform(value))
  return {
    unit,
    format,
    measure: (value) =>
      unit === "%" ? `${format(value)}%` : joinMeasure(format(value), unit),
  }
}

/** Vietnamese decimal punctuation, a true minus sign, and no trailing zeroes. */
function decimal(value: number): string {
  const rounded = Math.abs(value) < 0.05 ? 0 : value
  return plainLocale(rounded).replace(/^-/, "−")
}

function plainLocale(value: number): string {
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  })
}

/** A non-breaking space is part of the measurement, not layout decoration. */
function joinMeasure(value: string, unit: string): string {
  return unit === "" ? value : `${value}\u00a0${unit}`
}
