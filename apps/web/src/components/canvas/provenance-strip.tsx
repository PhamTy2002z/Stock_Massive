"use client"

/**
 * Where the numbers came from, when they were frozen, and how thin the window is.
 *
 * Four facts on one line, and they are shown together because none of them
 * answers the reader's question alone. A date without the session count does not
 * say whether the picture is of a habit or a fortnight; a session count without
 * the health does not say whether those sessions were whole.
 *
 * **The age is said out loud.** `asOf` is frozen when the Study ran, so a Thread
 * re-opened next week renders the same picture — correctly — and a reader
 * glancing at it would read it as today. So the strip does not merely print a
 * date, it says how old it is. Anything under a day is left as the date alone:
 * "hôm nay" beside a full timestamp is noise.
 */

import type { Provenance } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/** What each health value means to a reader, in the words the lane already uses. */
const HEALTH: Record<Provenance["health"], { label: string; tone: string }> = {
  normal: { label: "đầy đủ", tone: "text-muted-foreground" },
  degraded: { label: "thiếu một phần", tone: "text-caution" },
  unavailable: { label: "không đọc được", tone: "text-negative" },
}

export function ProvenanceStrip({ provenance }: { provenance: Provenance }) {
  const health = HEALTH[provenance.health] ?? HEALTH.normal
  const day = readableDay(provenance.asOf)
  const age = ageInDays(provenance.asOf)

  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-meta text-muted-foreground">
      <span>{provenance.source}</span>
      <span aria-hidden>·</span>
      <span>
        dữ liệu {day}
        {age !== null && age >= 1 && ` (${age} ngày trước)`}
      </span>
      <span aria-hidden>·</span>
      <span>{provenance.sessionsUsed} phiên</span>
      <span aria-hidden>·</span>
      <span className={cn(health.tone)}>{health.label}</span>
      {provenance.reason !== null && provenance.reason !== "" && (
        <>
          <span aria-hidden>·</span>
          <span>{provenance.reason}</span>
        </>
      )}
    </p>
  )
}

/** The as-of as a Vietnamese date, or the raw string if it is not one. */
function readableDay(asOf: string): string {
  const moment = new Date(asOf)
  if (Number.isNaN(moment.getTime())) return asOf
  return moment.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

/** How many whole days ago the numbers were frozen, or null if unreadable. */
function ageInDays(asOf: string): number | null {
  const moment = new Date(asOf)
  if (Number.isNaN(moment.getTime())) return null
  return Math.floor((Date.now() - moment.getTime()) / 86_400_000)
}
