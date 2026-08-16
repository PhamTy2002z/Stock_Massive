"use client"

import { ChevronDown, Loader2 } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ACTIVITY_COPY } from "@/lib/alpha-desk/copy"
import type { ActivityPhase } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * One collapsed line while tools run, and nothing else.
 *
 * The publisher sends a phase and only a phase, so there is nothing here to
 * leak even by accident — no tool name, no symbol, no argument, no result
 * (`docs/specs/0002` §6, §9). Expanding gives a compact user-facing summary of
 * the *kind* of work, not a longer trace: the Tool Call Trace is the audit
 * surface, and it is reached deliberately rather than by being curious about a
 * spinner.
 *
 * One line, not a list. A running feed of steps is a trace with a friendlier
 * font, and it teaches the catalog the same way a trace would.
 */
export function ActivityLine({
  phase,
  className,
}: {
  phase: ActivityPhase
  className?: string
}) {
  const copy = ACTIVITY_COPY[phase]

  return (
    <Collapsible className={cn("overflow-hidden rounded-xl border border-border bg-surface-raised", className)}>
      <div className="flex items-center gap-2 px-3 py-2.5 text-meta text-muted-foreground">
        <Loader2 className="h-3 w-3 shrink-0 animate-spin motion-reduce:animate-none" />
        {/* `status` rather than `alert`: it is progress, and a screen reader
            should hear it when it next pauses, not be interrupted by it. */}
        <span role="status" className="min-w-0 flex-1 truncate">
          {copy.line}
        </span>
        {/* English, like every other control on this surface: the phase above
            it is the system narrating, and this is a button. */}
        <CollapsibleTrigger className="group inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors hover:bg-foreground/[0.06] hover:text-foreground">
          Details
          <ChevronDown className="h-3 w-3 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none" />
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent>
        <p className="border-t border-border px-3 py-2.5 text-meta text-muted-foreground">
          {copy.summary}
        </p>
      </CollapsibleContent>
    </Collapsible>
  )
}
