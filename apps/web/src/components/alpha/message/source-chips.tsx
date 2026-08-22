"use client"

import { cn } from "@/lib/utils"
import { SourceIcon } from "./source-icon"

/**
 * A stack of source marks beside a result count.
 *
 * Overlapped rather than spaced, and capped at a few: this is a glance, not a
 * list. It says *the answer went and looked, at these sorts of places* — the
 * list itself is one click away, and crowding every source in here would make
 * the row unreadable while telling the reader nothing they could act on.
 *
 * The ring is the page's own ground colour, which is what makes the overlap
 * read as a stack of discs rather than as one clipped shape.
 */
export function SourceChips({
  sources,
  max = 3,
  className,
}: {
  sources: string[]
  max?: number
  className?: string
}) {
  const shown = sources.slice(0, max)
  if (shown.length === 0) return null

  return (
    <span className={cn("flex items-center pl-[5px]", className)}>
      {shown.map((source, index) => (
        <SourceIcon
          key={`${source}-${index}`}
          source={source}
          className="-ml-[5px] ring-[1.5px] ring-background"
        />
      ))}
    </span>
  )
}
