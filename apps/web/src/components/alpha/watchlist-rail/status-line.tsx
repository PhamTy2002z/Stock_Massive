"use client"

import { AlertTriangle } from "lucide-react"

import { cn } from "@/lib/utils"
import { missingSessionNotice } from "./state-copy"

/**
 * One system-level status line for the whole rail, or nothing.
 *
 * It answers "why is today not on the rail yet", which is a fact about the
 * collection run rather than about any symbol. Rendered per symbol it would
 * read as ten separate problems; rendered always it would be chrome nobody
 * reads by the second week.
 *
 * `now` is a parameter so the condition is testable without a fake clock. It
 * defaults to the real one, and nothing else in this component reads a clock.
 */
export function SystemStatusLine({
  tradingDay,
  now,
  className,
}: {
  tradingDay: string | null
  now?: Date
  className?: string
}) {
  const notice = missingSessionNotice(tradingDay, now)
  if (!notice) return null

  return (
    <p
      role="status"
      className={cn(
        "flex items-center gap-2 rounded-md border border-caution/40 bg-caution/5 px-3 py-2 text-xs text-caution",
        className,
      )}
    >
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      {notice}
    </p>
  )
}
