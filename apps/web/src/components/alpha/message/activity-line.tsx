"use client"

import { BarChart3, ChevronDown, Database, Scale, Search } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ACTIVITY_COPY } from "@/lib/alpha-desk/copy"
import type { ActivityPhase } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * How the Turn is working, as the reader watches it: the steps it has finished,
 * then the one it is on.
 *
 * **Semantic, never a trace.** The publisher sends a phase and only a phase, so
 * there is nothing here to leak even by accident — no tool name, no symbol, no
 * argument, no result (`docs/specs/0002` §6, §9). What the trail adds over a
 * single line is *that the work had parts*; what it must never become is the
 * way a curious reader learns the catalog. Expanding a step gives the same
 * compact summary the collapsed line always gave, and the Tool Call Trace stays
 * the audit surface, reached deliberately.
 *
 * The finished steps stay because a step that vanished as the next one started
 * left the reader with a spinner that changed its mind — the point of showing
 * work is that the work is legible after it happened.
 */
export function ActivityTrail({
  steps,
  phase,
  className,
}: {
  /** Finished, in the order they finished. */
  steps: ActivityPhase[]
  /** What is running now, or null between steps and after the last one. */
  phase: ActivityPhase | null
  className?: string
}) {
  if (steps.length === 0 && phase === null) return null

  return (
    <div className={cn("grid gap-2.5", className)}>
      {steps.map((step, index) => (
        <FinishedStep key={`${step}-${index}`} phase={step} />
      ))}
      {phase !== null && <ActivityLine phase={phase} />}
    </div>
  )
}

/** The icon each phase carries once it is a step rather than a spinner. */
const STEP_ICON: Record<ActivityPhase, typeof Search> = {
  searching: Search,
  reading_data: Database,
  analyzing: Scale,
  preparing_visual: BarChart3,
}

/**
 * One finished step: an icon, what it did, and the summary behind it.
 *
 * No `status` role. It is not progress any more — announcing every completed
 * step would turn a quiet answer into a queue of interruptions, and the live
 * line below is the one thing a screen reader still has to hear.
 */
function FinishedStep({ phase }: { phase: ActivityPhase }) {
  const copy = ACTIVITY_COPY[phase]
  const Icon = STEP_ICON[phase]

  return (
    <Collapsible className="animate-vg-row-in">
      <CollapsibleTrigger className="group flex w-full items-center gap-2 text-left text-meta text-muted-foreground transition-colors hover:text-foreground">
        <Icon className="size-3.5 shrink-0" strokeWidth={1.5} aria-hidden />
        <span className="min-w-0 flex-1 truncate">{copy.done}</span>
        <ChevronDown className="size-3 shrink-0 opacity-0 transition-[transform,opacity] group-hover:opacity-100 group-data-[state=open]:rotate-180 group-data-[state=open]:opacity-100 motion-reduce:transition-none" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <p className="pl-[22px] pt-1 text-meta text-ink-5">{copy.summary}</p>
      </CollapsibleContent>
    </Collapsible>
  )
}

/**
 * The step in flight: three pulsing dots and what it is doing.
 *
 * Dots rather than a spinner, and unboxed rather than in a card: this sits
 * between the question and the first block, where a bordered panel reads as
 * content that arrived instead of as work still happening.
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
    <Collapsible className={cn("animate-vg-row-in", className)}>
      <CollapsibleTrigger className="group flex w-full items-center gap-2 text-left text-meta text-muted-foreground transition-colors hover:text-foreground">
        <span className="flex shrink-0 items-center gap-1" aria-hidden>
          {[0, 1, 2].map((index) => (
            <i
              key={index}
              className="block size-1.5 animate-vg-dot-pulse rounded-full bg-primary motion-reduce:animate-none"
              style={{ animationDelay: `${index * 0.16}s` }}
            />
          ))}
        </span>
        {/* `status` rather than `alert`: it is progress, and a screen reader
            should hear it when it next pauses, not be interrupted by it. */}
        <span role="status" className="min-w-0 flex-1 truncate">
          {copy.line}
        </span>
        <ChevronDown className="size-3 shrink-0 opacity-0 transition-[transform,opacity] group-hover:opacity-100 group-data-[state=open]:rotate-180 group-data-[state=open]:opacity-100 motion-reduce:transition-none" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <p className="pl-[26px] pt-1 text-meta text-ink-5">{copy.summary}</p>
      </CollapsibleContent>
    </Collapsible>
  )
}
