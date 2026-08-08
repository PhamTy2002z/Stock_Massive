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

export function formatSessionDate(dateStr: string | undefined): string {
  if (!dateStr) return ""
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
}
