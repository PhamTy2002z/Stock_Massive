"use client"

import { cn } from "@/lib/utils"

/**
 * One material figure: its value, its unit, and when it was true.
 *
 * Used wherever a figure is shown behind a claim — the citation panel at the end
 * of the sentence it supports — because a figure that rendered its unit in one
 * place and not the other would be the exact failure this system exists to
 * prevent: a number the reader cannot weigh.
 *
 * Staleness is stated rather than styled away. A figure the system knows is old
 * is still usable; one silently presented as current is not.
 */
export function Figure({
  value,
  unit,
  asOf,
  stale,
  sourceName,
  retrievedAt,
  className,
}: {
  value: unknown
  unit: string | null
  asOf: string | null
  stale: boolean
  sourceName?: string | null
  retrievedAt?: string | null
  className?: string
}) {
  return (
    <span className={cn("flex flex-wrap items-baseline gap-x-2", className)}>
      <span className="font-medium tabular-nums">{displayValue(value)}</span>
      {unit && <span className="text-muted-foreground">{unit}</span>}
      {sourceName ? (
        <>
          <span className="rounded-md border border-caution/40 px-1 text-[10px] text-caution">
            Nguồn ngoài · chưa kiểm chứng
          </span>
          <span className="text-muted-foreground">
            {sourceName}
            {retrievedAt ? ` · retrieved ${retrievedAt}` : ""}
          </span>
        </>
      ) : (
        asOf && <span className="text-muted-foreground tabular-nums">as of {asOf}</span>
      )}
      {stale && (
        <span className="rounded-md border border-caution/40 px-1 text-[10px] text-caution">
          stale
        </span>
      )}
    </span>
  )
}

/**
 * A citation's value as text.
 *
 * `unknown` because that is what it is: a registered field may hold a number, a
 * label or a small structure, and the wire type says so honestly rather than
 * asserting a number that is sometimes not one. A missing value renders as a
 * dash — never as `null`, and never as an empty cell that reads as "nothing to
 * see" when the reason is "the system could not prove it".
 */
export function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "number") return value.toLocaleString("vi-VN")
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}
