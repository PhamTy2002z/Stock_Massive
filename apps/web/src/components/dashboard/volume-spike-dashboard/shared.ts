// Format helpers for the spike table.

export function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value.toLocaleString("vi-VN")
}

export function formatRatio(value: number): string {
  return `${value.toFixed(1)}x`
}

/**
 * How loud a spike is, as a colour.
 *
 * Thresholds rather than a stored severity level: the API answers with a ratio
 * and a threshold the reader chose, so a band computed here follows whatever
 * they asked for instead of a scale the server fixed in advance.
 */
export function ratioColor(ratio: number): string {
  if (ratio >= 3) return "text-red-500"
  if (ratio >= 2) return "text-amber-500"
  return "text-foreground"
}
