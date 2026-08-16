"use client"

import { formatFieldValue, unitLabel } from "@/components/alpha/widgets/units"
import type { FigureView } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import { CHROME, HEALTH_LABEL, HEALTH_TONE, NARRATION } from "./copy"

/**
 * One figure, with everything a reader needs to weigh it.
 *
 * Label, value, unit, `kind`, `source`, the sanctioned interpretation, an
 * `asOf` staleness stamp, and `health` with its reason when it is not `ok`
 * (`docs/specs/0002` §5). None of it is behind a disclosure and none of it is
 * in a tooltip: a `degraded`, `insufficient_history` or `refused` figure is
 * honesty evidence, and evidence a reader has to hover to find is evidence the
 * artifact is hiding.
 *
 * **The reason is rendered, the code is not.** `reason` arrives already
 * translated from the one place that holds the Signal Issue vocabulary, so
 * nothing here can put `insufficient_history` on a screen.
 *
 * A refused figure shows `—` where its value would be and says, in words, that
 * it cannot support the verdict. Blank would read as "nothing to see"; the
 * whole point is that there is something to see and it is an absence.
 */
export function FigureRow({
  figure,
  /** The expanded treatment names the registered field; the inline one counts. */
  showFieldId = false,
  className,
}: {
  figure: FigureView
  showFieldId?: boolean
  className?: string
}) {
  const refused = figure.health === "refused"
  const unit = unitLabel(figure.unit)

  return (
    <div
      className={cn(
        "space-y-1 border-l-2 py-1 pl-2",
        HEALTH_TONE[figure.health].border,
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-xs font-medium">{figure.label}</span>
        <span className="text-sm font-semibold tabular-nums">
          {formatFieldValue(figure.value, figure.unit)}
        </span>
        {unit && <span className="text-[11px] text-muted-foreground">{unit}</span>}
        {figure.cited && (
          <span
            className="rounded border border-primary/40 px-1 text-[10px] text-primary"
            title={CHROME.citations}
          >
            cited
          </span>
        )}
        <span
          className={cn("rounded border px-1 text-[10px]", HEALTH_TONE[figure.health].badge)}
        >
          {HEALTH_LABEL[figure.health]}
        </span>
      </div>

      <p className="flex flex-wrap gap-x-2 text-[11px] text-muted-foreground">
        {figure.kind && <span>{figure.kind}</span>}
        {figure.source && <span>· {figure.source}</span>}
        <span>
          · {CHROME.asOf} <span className="tabular-nums">{figure.asOf ?? "—"}</span>
        </span>
        {figure.sessionsUsed !== null && (
          <span className="tabular-nums">
            · {figure.sessionsUsed} {CHROME.sessions}
          </span>
        )}
        {figure.windowDays !== null && (
          <span className="tabular-nums">
            · {CHROME.window} {figure.windowDays}
          </span>
        )}
      </p>

      {figure.interpretation && (
        <p className="text-[11px] leading-snug text-muted-foreground">
          {figure.interpretation}
        </p>
      )}

      {figure.reason && (
        <p className="text-[11px] leading-snug">
          {figure.reason}
          {refused && (
            <span className="text-muted-foreground"> · {NARRATION.refusedIsEvidence}</span>
          )}
        </p>
      )}

      {showFieldId && (
        <p className="font-mono text-[10px] text-muted-foreground">{figure.fieldId}</p>
      )}
    </div>
  )
}
