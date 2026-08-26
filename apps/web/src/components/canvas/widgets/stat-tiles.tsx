"use client"

/**
 * The few numbers that lead, one tile per row of the frame.
 *
 * Drawn from a frame rather than from the headline the model was given, which
 * is the arrangement rather than an inconvenience: the headline is prose input
 * and could be paraphrased, and what a reader is shown has to be the same
 * numbers the picture underneath is drawn from. So the Study writes a `tiles`
 * frame and this reads it.
 *
 * No chart library. Four numbers in boxes is layout, and pulling a charting
 * runtime in to place them would cost the panel its first paint.
 */

import { columnIndex, formatNumber, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"

export function StatTilesWidget({ frame, options }: WidgetProps) {
  const label = columnIndex(frame, options.label ?? "label")
  const value = columnIndex(frame, options.value ?? "value")
  const unit = columnIndex(frame, options.unit ?? "unit")

  if (frame.rows.length === 0) {
    return <p className="text-meta text-muted-foreground">Chưa có số dẫn dắt nào.</p>
  }

  return (
    <dl className="grid grid-cols-2 gap-2">
      {frame.rows.map((row, index) => (
        <div
          key={index}
          className="rounded-lg border border-hairline bg-surface-sunken px-3 py-2.5"
        >
          <dt className="truncate text-meta text-muted-foreground">
            {textAt(row, label)}
          </dt>
          <dd className="mt-0.5 flex items-baseline gap-1">
            <span className="truncate text-base font-medium tabular-nums text-foreground">
              {reading(row[value])}
            </span>
            {unit >= 0 && typeof row[unit] === "string" && row[unit] !== "" && (
              <span className="text-meta text-muted-foreground">{row[unit]}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** A tile's value: a number formatted, a label kept, and nothing invented. */
function reading(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return formatNumber(value)
  if (typeof value === "string" && value !== "") return value
  return "—"
}
