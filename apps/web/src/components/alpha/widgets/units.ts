/**
 * How a registered field's value is written, given the unit the server sent.
 *
 * The unit is the server's — it comes off the Signal Registry through the
 * validated spec — and this module only decides how many digits and which
 * suffix. Nothing here converts: a Widget that rescaled a figure would be a
 * Widget changing a unit, which is exactly what ADR-0012 keeps on the server.
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

export function formatFieldValue(value: number | null, unit: string | null): string {
  if (value === null || Number.isNaN(value)) return "—"
  switch (unit) {
    case "percent":
    case "percent_annualized":
      return `${decimals(value, 2)}%`
    case "percentile":
      return `${decimals(value, 1)}` // already a 0–100 rank; the axis says so
    case "index_0_100":
      return decimals(value, 1)
    case "ratio":
    case "z_score":
      return decimals(value, 2)
    case "sessions":
      return `${decimals(value, 0)} phiên`
    case "shares":
      return `${decimals(value, 0)} cp`
    case "vnd": {
      const scale = VND_SCALES.find(([bound]) => Math.abs(value) >= bound)
      return scale
        ? `${decimals(value / scale[0], 2)} ${scale[1]}`
        : `${decimals(value, 0)} đ`
    }
    default:
      return decimals(value, 2)
  }
}

/** The unit as a short axis label, for the picture rather than the figure. */
export function unitLabel(unit: string | null): string {
  switch (unit) {
    case "percent":
      return "%"
    case "percent_annualized":
      return "%/năm"
    case "percentile":
      return "phân vị"
    case "index_0_100":
      return "chỉ số 0–100"
    case "z_score":
      return "z"
    case "ratio":
      return "lần"
    case "sessions":
      return "phiên"
    case "shares":
      return "cp"
    case "vnd":
      return "đồng"
    default:
      return unit ?? ""
  }
}
