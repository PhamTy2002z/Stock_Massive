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
 *
 * `heading` and `glance` are what the reference wraps that in — a greeting and
 * a look at where the market stands. Both are injected rather than fetched
 * here, because both need hooks and this component is rendered by a transcript
 * that is deliberately presentational; without them the surface still opens on
 * its question and its two rules, which is the part that matters.
 */
export function FirstRun({
  heading,
  glance,
  className,
}: {
  /** Replaces the opening question — the container passes a greeting. */
  heading?: React.ReactNode
  /** A quiet line under the copy: where the indices stand right now. */
  glance?: React.ReactNode
  className?: string
}) {
  return (
    <section
      aria-label="Alpha Desk"
      className={cn("mx-auto w-full max-w-[760px] space-y-5 px-4 py-10", className)}
    >
      {heading ?? (
        <h2 className="text-[clamp(1.24rem,2.1vw,1.6rem)] font-normal tracking-[-0.015em] text-foreground">
          {FIRST_RUN.question}
        </h2>
      )}

      <div className="space-y-3 rounded-card border border-border bg-card p-4 text-control text-muted-foreground">
        <p>{FIRST_RUN.universeRule}</p>
        <p>{FIRST_RUN.scopeBoundary}</p>
      </div>

      <p className="text-meta text-muted-foreground">{FIRST_RUN.hint}</p>

      {glance}
    </section>
  )
}
