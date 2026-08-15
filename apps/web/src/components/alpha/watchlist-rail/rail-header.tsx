"use client"

import { CalendarDays } from "lucide-react"

import { cn } from "@/lib/utils"
import { sessionLabel } from "./state-copy"

/**
 * The band above the rail: which session it is showing, and how full it is.
 *
 * The session is named by date and never called "today" — the latest session
 * with a Snapshot is frequently not today, and a rail labelled "today" while
 * showing Friday's data is wrong in the one place a user checks first.
 *
 * The cap is a permanent count rather than an error at the eleventh add. Users
 * collide with this limit every time they add a symbol, so hiding it until it
 * bites turns the first collision into a surprise.
 */
export function RailHeader({
  tradingDay,
  count,
  cap,
  className,
}: {
  tradingDay: string | null
  count: number
  cap: number
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-2", className)}>
      <div className="flex items-center gap-2 text-sm">
        <CalendarDays className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium">Watchlist</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-muted-foreground">{sessionLabel(tradingDay)}</span>
      </div>
      <span
        className={cn(
          "rounded-md border px-2 py-0.5 text-xs tabular-nums",
          // Over the cap is a real state: a symbol restored to the Universe
          // revives whether or not there is room, and the overflow stands.
          count > cap
            ? "border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400"
            : "border-border/60 text-muted-foreground",
        )}
        aria-label={`${count} of ${cap} symbols`}
      >
        {count}/{cap}
      </span>
    </div>
  )
}
