// Shared display formatters (Vietnamese locale conventions).
// Only formatters whose duplicated copies were semantically identical are
// consolidated here — components with divergent formatting keep local versions.

export function formatVolume(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

export function formatPercent(value: number | null): string {
  // An em dash, like `units.ts` and `frame.ts` and every other absent value in
  // the product. A hyphen here read as a minus sign in a column of signed
  // percentages — the one place in this interface where the wrong glyph does
  // not merely look inconsistent but states a direction the data never had.
  if (value === null) return "—"
  // Rounded first, then signed. `-0.001` is negative, so the sign test skips
  // the plus, and `toFixed(2)` rounds it to `0.00` — which printed "-0.00%",
  // a fall the reader cannot act on dressed as a fall. Deciding the sign from
  // the number that actually gets printed keeps the two in agreement.
  const rounded = Number(value.toFixed(2))
  const shown = rounded === 0 ? 0 : rounded
  return `${shown >= 0 ? "+" : ""}${shown.toFixed(2)}%`
}

export function formatBillions(value: number): string {
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  // Explicitly Vietnamese, like every other number in this file. Bare
  // `toLocaleString()` takes the *browser's* locale, so the same figure was
  // grouped "1.234" for a reader in Hanoi and "1,234" for the same account
  // opened abroad — with the separators swapped, which is the one difference
  // that changes what the digits say.
  return value.toLocaleString("vi-VN")
}

/** Age units from coarsest down, so the first that fits is the one to name. */
const AGE_UNITS = [
  { seconds: 86_400, label: "ngày" },
  { seconds: 3_600, label: "giờ" },
  { seconds: 60, label: "phút" },
] as const

/**
 * How old a stored figure is, in the coarsest unit that still says something.
 *
 * The API reports age in seconds from the session the data describes, so an
 * evening read of the session that just closed is already tens of thousands of
 * seconds old — a number no reader can weigh. The remainder is not dropped
 * silently: "1 ngày" for 47 hours would make the data look half its age, so a
 * partial unit is said out loud as "hơn". Rounding up instead would age data
 * the collector has only just written.
 */
export function formatDataAge(ageSeconds: number): string {
  const seconds = Math.max(0, Math.floor(ageSeconds))
  const unit = AGE_UNITS.find((candidate) => seconds >= candidate.seconds)
  if (!unit) return "dưới 1 phút"
  const count = Math.floor(seconds / unit.seconds)
  const prefix = seconds % unit.seconds === 0 ? "" : "hơn "
  return `${prefix}${count} ${unit.label}`
}
