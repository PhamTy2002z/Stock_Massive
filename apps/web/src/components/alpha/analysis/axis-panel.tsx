"use client"

import type { AxisView } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import {
  AXIS_LABEL,
  CHROME,
  EMPHASIS_LABEL,
  HEALTH_LABEL,
  HEALTH_TONE,
  NARRATION,
} from "./copy"
import { FigureRow } from "./figure-row"

/**
 * One axis: what the model read into it, and the figures it read.
 *
 * The panel never decides where it sits. Its axis, its emphasis and its
 * position are handed to it by the projection, which builds the four in a fixed
 * order — so an axis cannot lift itself up the artifact by being the lead.
 * Emphasis shows up here as heading weight and, in the inline treatment, as
 * which tab was already open.
 *
 * `emphasisReason` and `read` are the model's narration and are Vietnamese; the
 * axis name, the emphasis word and the health word are chrome and are English.
 */
export function AxisPanel({
  axis,
  showFieldIds = false,
  className,
}: {
  axis: AxisView
  showFieldIds?: boolean
  className?: string
}) {
  return (
    <section className={cn("space-y-2", className)} aria-label={AXIS_LABEL[axis.axis]}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <h4
          className={cn(
            "text-xs uppercase tracking-wide",
            axis.emphasis === "lead" ? "font-semibold" : "font-medium text-muted-foreground",
          )}
        >
          {AXIS_LABEL[axis.axis]}
        </h4>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {EMPHASIS_LABEL[axis.emphasis]}
        </span>
        <span
          className={cn("rounded border px-1 text-[10px]", HEALTH_TONE[axis.health].badge)}
        >
          {HEALTH_LABEL[axis.health]}
        </span>
      </div>

      {axis.read ? (
        <p className="text-[13px] leading-relaxed">{axis.read}</p>
      ) : (
        <p className="text-[13px] text-muted-foreground">{NARRATION.noRead}</p>
      )}

      {axis.emphasisReason && (
        <p className="text-[11px] text-muted-foreground">{axis.emphasisReason}</p>
      )}

      {axis.figures.length > 0 ? (
        <div className="space-y-1.5">
          {axis.figures.map((figure) => (
            <FigureRow
              key={figure.fieldId}
              figure={figure}
              showFieldId={showFieldIds}
            />
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">{CHROME.noFigures}</p>
      )}
    </section>
  )
}
