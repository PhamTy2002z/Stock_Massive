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
 * A number at a width a reader can take in at a glance.
 *
 * Vietnamese grouping, and the magnitude suffixes a board uses: a bucket
 * average of 4.242.424 shares says less at a glance than "4,24 tr". Below ten
 * thousand nothing is abbreviated — the digits are already readable, and
 * rounding them would hide the difference between 812 and 1.204.
 */
export function formatNumber(value: number): string {
  const magnitude = Math.abs(value)
  if (magnitude >= 1e9) return `${(value / 1e9).toLocaleString("vi-VN", DECIMALS)} tỷ`
  if (magnitude >= 1e6) return `${(value / 1e6).toLocaleString("vi-VN", DECIMALS)} tr`
  if (magnitude >= 1e4) return `${(value / 1e3).toLocaleString("vi-VN", DECIMALS)} ng`
  return value.toLocaleString("vi-VN", { maximumFractionDigits: 2 })
}

const DECIMALS: Intl.NumberFormatOptions = {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}

/** A share of a whole, as the percentage a reader expects. */
export function formatPercent(value: number): string {
  return `${(value * 100).toLocaleString("vi-VN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`
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
