"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Globe } from "lucide-react"

import { PROGRESS_COPY } from "@/lib/alpha-desk/copy"
import type { ActivityPhase, ProgressStep } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { SourceList } from "./source-list"

/**
 * How the Turn worked, as a trail the reader can open or fold away.
 *
 * One component for both halves of the answer's life. While the Turn runs it is
 * open and growing; once the answer is there it collapses to a single quiet line
 * above it, because the trail is *how* rather than *what* and an answered
 * question should read as an answer.
 *
 * **The rows are semantic except where `docs/adr/0020` says otherwise.** A step
 * from a store-reading lane carries a phase and nothing else, exactly as
 * ADR-0013 required. An open-web step also carries the sentence it searched for
 * and the public pages it found — both public, both things the reader needs in
 * order to weigh an answer built on them.
 *
 * The vertical rule is drawn by the rows rather than by a container so the last
 * row can end it: a line running past the final dot reads as a step that has not
 * arrived yet, which on a finished Turn is a lie about the work.
 */
export function SearchProgress({
  steps,
  activity,
  ending = null,
  defaultOpen = false,
  className,
}: {
  steps: ProgressStep[]
  /** The phase running now, or null on a Turn that has stopped. */
  activity: ActivityPhase | null
  /** The closing row: what the Turn ended as, or null while it is still going. */
  ending?: "done" | "stopped" | null
  /** Open while the work is happening; folded once the answer is on screen. */
  defaultOpen?: boolean
  className?: string
}) {
  const rows = visibleRows(steps, activity)
  const [open, setOpen] = useState(defaultOpen)

  // The trail folds itself the moment the Turn ends, rather than waiting for the
  // canonical message to replace the draft that opened it. Between those two
  // things is a gap the reader spends looking at an answer with the machinery
  // still spread open above it. Adjusted during render off the previous
  // `ending` — an effect would fold on a second pass, one frame late.
  const [endedAs, setEndedAs] = useState(ending)
  if (ending !== endedAs) {
    setEndedAs(ending)
    if (ending !== null) setOpen(false)
  }

  // No step worth naming means no trail, even on a Turn that finished: a
  // disclosure whose only row is *Hoàn thành* discloses nothing.
  if (rows.length === 0) return null

  return (
    <div className={cn("grid gap-3", className)}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="group flex w-fit items-center gap-1.5 text-left text-[0.95rem] text-ink-5 transition-colors hover:text-ink-3"
      >
        {PROGRESS_COPY.header}
        {open ? (
          <ChevronDown className="size-4 shrink-0" strokeWidth={1.8} />
        ) : (
          <ChevronRight className="size-4 shrink-0" strokeWidth={1.8} />
        )}
      </button>

      {open && (
        <ol className="grid">
          {rows.map(({ step, running, index }) => (
            <TrailRow
              key={`${step.phase}-${index}`}
              label={labelOf(step, running)}
              running={running}
              last={ending === null && index === rows[rows.length - 1].index}
            >
              <StepDetail step={step} />
            </TrailRow>
          ))}

          {ending !== null && (
            <TrailRow
              label={ending === "done" ? PROGRESS_COPY.done : PROGRESS_COPY.stopped}
              running={false}
              last
            />
          )}
        </ol>
      )}
    </div>
  )
}

/**
 * One dot, one label, and whatever the step disclosed under it.
 *
 * The dot is `1rem` from the left and the rule sits under its centre, so the
 * indented content lines up with the label rather than with the bullet — the
 * reader's eye follows the labels down, and the detail hangs off them.
 */
function TrailRow({
  label,
  running,
  last,
  children,
}: {
  label: string
  running: boolean
  last: boolean
  children?: React.ReactNode
}) {
  return (
    <li className="relative grid gap-2 pb-5 pl-7 last:pb-0">
      {/* The rule, drawn from this row's dot down to the next one. Absent on
          the last row, where a line to nowhere would promise another step. */}
      {!last && (
        <span
          aria-hidden
          className="absolute bottom-0 left-[3px] top-3 w-px bg-border"
        />
      )}
      <span
        aria-hidden
        className={cn(
          "absolute left-0 top-[7px] size-[7px] rounded-full",
          running ? "animate-vg-dot-pulse bg-primary motion-reduce:animate-none" : "bg-ink-6",
        )}
      />
      <span
        // `status` rather than `alert` on the live row: it is progress, and a
        // screen reader should hear it at the next pause rather than be
        // interrupted by it. Finished rows announce nothing at all.
        role={running ? "status" : undefined}
        className={cn("text-[0.95rem] leading-6", running ? "text-ink-3" : "text-ink-5")}
      >
        {label}
      </span>
      {children}
    </li>
  )
}

/** The open-web disclosure: what was asked, then what came back. */
function StepDetail({ step }: { step: ProgressStep }) {
  const queries = step.detail?.queries ?? []
  const sources = step.detail?.sources ?? []
  const count = step.detail?.result_count ?? sources.length

  if (queries.length === 0 && sources.length === 0) return null

  return (
    <div className="grid gap-2 pt-1">
      {queries.length > 0 && (
        <>
          <p className="flex items-center gap-1.5 text-meta text-ink-5">
            <Globe className="size-3.5 shrink-0" strokeWidth={1.6} aria-hidden />
            {PROGRESS_COPY.queries}
          </p>
          <ul className="flex flex-wrap gap-2">
            {queries.map((query) => (
              <li
                key={query}
                className="rounded-lg bg-surface-raised px-2.5 py-1.5 text-meta text-ink-3"
              >
                {query}
              </li>
            ))}
          </ul>
        </>
      )}

      {sources.length > 0 && (
        <>
          <p className="text-meta text-ink-5">{PROGRESS_COPY.sourcesTitle(count)}</p>
          <SourceList sources={sources} />
        </>
      )}
    </div>
  )
}

/**
 * Whether this pair would draw a trail at all.
 *
 * Exported so a caller can tell an empty trail from a folded one. The draft
 * needs the difference: with nothing else on screen yet, a Turn whose only step
 * has been filtered away still owes the reader a sign that it is working.
 */
export function hasVisibleTrail(
  steps: ProgressStep[],
  activity: ActivityPhase | null,
): boolean {
  return visibleRows(steps, activity).length > 0
}

/** One step as it is drawn, keeping the index it had among all the steps. */
interface TrailItem {
  step: ProgressStep
  running: boolean
  /** Its position in `steps`, so *last* still means last of the real work. */
  index: number
}

/**
 * Which steps are worth a row.
 *
 * Only the newest step can be the running one: the phases arrive in order, and
 * a phase repeated later in the trail does not restart the earlier row.
 *
 * *Analyzing* is dropped unless it is that running step. It is the one phase
 * that names no work the reader can weigh — no query, no source, no count — so
 * once it is over it contributes a line that says the system was thinking about
 * an answer the reader is already looking at.
 */
function visibleRows(steps: ProgressStep[], activity: ActivityPhase | null): TrailItem[] {
  return steps
    .map((step, index) => ({
      step,
      index,
      running: activity === step.phase && index === steps.length - 1,
    }))
    .filter(({ step, running }) => step.phase !== "analyzing" || running)
}

/**
 * What one row says.
 *
 * Takes the whole step rather than its phase, because one row is a *number*:
 * *Đã tìm thấy 15 kết quả* is what the reader weighs the answer against, and it
 * lives in the detail beside the phase that earned it.
 *
 * It also takes whether the row is the live one, because a step that is over
 * says so. *Đang tìm trên web…* above a finished answer describes a Turn that
 * is still running, which is the thing the reader is trying to find out.
 */
function labelOf(step: ProgressStep, running: boolean): string {
  switch (step.phase) {
    case "searching":
      return running ? PROGRESS_COPY.searching : PROGRESS_COPY.searched
    case "found_sources":
      // Already a finished fact in both states: the count is what came back.
      return PROGRESS_COPY.found(
        step.detail?.result_count ?? step.detail?.sources?.length ?? 0,
      )
    case "reading_data":
      return running ? PROGRESS_COPY.readingData : PROGRESS_COPY.readData
    case "preparing_visual":
      return running ? PROGRESS_COPY.preparingVisual : PROGRESS_COPY.preparedVisual
    case "analyzing":
      // Only ever drawn while it is the running step; see `visibleRows`.
      return PROGRESS_COPY.thinking
  }
}
