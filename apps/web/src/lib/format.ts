// Shared display formatters (Vietnamese locale conventions).
// Only formatters whose duplicated copies were semantically identical are
// consolidated here — components with divergent formatting keep local versions.

export function formatVolume(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

export function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

export function formatBillions(value: number): string {
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toLocaleString()
}

/**
 * How old a stored figure is, in the coarsest unit that still says something.
 *
 * The API reports age in seconds from the session the data describes, so an
 * evening read of the session that just closed is already tens of thousands of
 * seconds old — a number no reader can weigh. Rounding down is deliberate: "1
 * ngày" for 47 hours understates nothing the reader cares about, while rounding
 * up would age data the collector has just written.
 */
export function formatDataAge(ageSeconds: number): string {
  const seconds = Math.max(0, ageSeconds)
  if (seconds < 60) return "dưới 1 phút"
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} giờ`
  return `${Math.floor(seconds / 86400)} ngày`
}

export function formatSessionDate(dateStr: string | undefined): string {
  if (!dateStr) return ""
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
}
