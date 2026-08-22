/**
 * How a registered field's value is written, given the unit the server sent.
 *
 * The unit is the server's — it comes off the Signal Registry with the figure —
 * and this module only decides how many digits and which suffix. Nothing here
 * converts: a client that rescaled a figure would be a client changing a unit,
 * and the unit is part of what was measured.
 *
 * One record rather than two switches over the same strings. Two cascades on
 * one union is how a unit ends up formatted here and labelled as something else
 * three lines down, and the pair is what a reader actually sees together.
 */

const VND_SCALES: [number, string][] = [
  [1_000_000_000_000, "nghìn tỷ"],
  [1_000_000_000, "tỷ"],
  [1_000_000, "triệu"],
]

function decimals(value: number, digits: number): string {
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function money(value: number): string {
  const scale = VND_SCALES.find(([bound]) => Math.abs(value) >= bound)
  return scale ? `${decimals(value / scale[0], 2)} ${scale[1]}` : `${decimals(value, 0)} đ`
}

interface UnitStyle {
  /** How one value of this unit is written out. */
  format: (value: number) => string
  /** The short form an axis or a column header carries. */
  label: string
}

/** Every unit the Signal Registry declares, and how each is read. */
const UNITS: Record<string, UnitStyle> = {
  percent: { format: (v) => `${decimals(v, 2)}%`, label: "%" },
  percent_annualized: { format: (v) => `${decimals(v, 2)}%`, label: "%/năm" },
  percent_per_billion_vnd: {
    format: (v) => `${decimals(v, 4)}%/tỷ`,
    label: "%/tỷ đồng",
  },
  // Already a 0–100 rank, so the axis says what it is rather than the figure.
  percentile: { format: (v) => decimals(v, 1), label: "phân vị" },
  index_0_100: { format: (v) => decimals(v, 1), label: "chỉ số 0–100" },
  z_score: { format: (v) => decimals(v, 2), label: "z" },
  ratio: { format: (v) => decimals(v, 2), label: "lần" },
  sessions: { format: (v) => `${decimals(v, 0)} phiên`, label: "phiên" },
  shares: { format: (v) => `${decimals(v, 0)} cp`, label: "cp" },
  vnd: { format: money, label: "đồng" },
}

/** What an unrecognised unit falls back to, so a new one is legible on sight. */
const UNKNOWN: UnitStyle = { format: (v) => decimals(v, 2), label: "" }

function styleOf(unit: string | null): UnitStyle {
  return (unit && UNITS[unit]) || UNKNOWN
}

export function formatFieldValue(value: number | null, unit: string | null): string {
  if (value === null || Number.isNaN(value)) return "—"
  return styleOf(unit).format(value)
}

/** The unit as a short axis label, for the picture rather than the figure. */
export function unitLabel(unit: string | null): string {
  const style = styleOf(unit)
  return style === UNKNOWN ? (unit ?? "") : style.label
}
