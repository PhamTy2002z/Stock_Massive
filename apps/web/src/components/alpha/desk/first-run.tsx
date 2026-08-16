"use client"

import { FIRST_RUN } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/**
 * The screen before the first question.
 *
 * It teaches two things and stops (`docs/specs/0002` §7): that any Universe
 * symbol may be discussed while only Watchlist symbols get nightly production,
 * and where the scope ends.
 *
 * **It publishes no catalog.** Listing what the agent can compute would turn
 * this into a menu, and a menu is a promise about every item on it — including
 * the ones a given symbol has no data for. A refusal names what is available at
 * the moment it matters, which is the only moment the list is accurate
 * (ADR-0011).
 */
export function FirstRun({ className }: { className?: string }) {
  return (
    <section
      aria-label="Alpha Desk"
      className={cn("mx-auto w-full max-w-[760px] space-y-5 px-4 py-14", className)}
    >
      <h2 className="text-[1.28rem] font-medium tracking-[-0.015em] text-foreground">{FIRST_RUN.question}</h2>

      <div className="space-y-3 rounded-card border border-border bg-card p-4 text-control text-muted-foreground">
        <p>{FIRST_RUN.universeRule}</p>
        <p>{FIRST_RUN.scopeBoundary}</p>
      </div>

      <p className="text-meta text-muted-foreground">{FIRST_RUN.hint}</p>
    </section>
  )
}
