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
 *
 * **The value speaks the magnitude and the unit speaks the unit.** They are two
 * cells of the frame and two spans on the tile, so the number carries its
 * magnitude as a word — "380 nghìn cp" — rather than as the axis shorthand
 * that ran straight into the unit beside it and read as two units.
 *
 * **Colour is the engine's claim, not decoration.** A tile is inked in the
 * foreground colour like the rest of the page unless the frame said what that
 * number is — a figure that rose, the one the answer is about — and then it
 * carries the colour for that. So a coloured tile on this grid always means
 * something was claimed, and the tile's own label and the table under the block
 * say the same thing in words.
 *
 * **The columns are counted from the panel, not from the viewport.** The
 * inspector is a column a reader drags, so a breakpoint would be measuring the
 * wrong thing: at 420 pixels of panel on a wide screen every breakpoint says
 * "wide" and the tiles stay two across regardless. `auto-fit` measures the grid
 * itself, which is the box the tiles are actually in.
 */

import { columnIndex, formatMeasureParts, formatUnit, pointRole, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { colorFor, resolveRoles } from "./chart-theme"

export function StatTilesWidget({ frame, options }: WidgetProps) {
  const label = columnIndex(frame, options.label ?? "label")
  const value = columnIndex(frame, options.value ?? "value")
  const unit = columnIndex(frame, options.unit ?? "unit")

  if (frame.rows.length === 0) {
    return <p className="text-meta text-muted-foreground">Chưa có số dẫn dắt nào.</p>
  }

  // A tile that says nothing keeps the ink it has always had. Only a tile the
  // engine said something about is coloured, so colour on this grid always
  // means the same thing: a claim was made about that number.
  const { roles } = resolveRoles(frame.rows.map((_, index) => pointRole(frame, index)))

  return (
    <dl className="grid grid-cols-[repeat(auto-fit,minmax(9rem,1fr))] gap-2">
      {frame.rows.map((row, index) => (
        <div key={index} className="rounded-lg border border-hairline bg-surface-sunken px-3 py-2.5">
          <dt className="truncate text-meta text-muted-foreground">
            {textAt(row, label)}
          </dt>
          <Reading
            value={row[value]}
            unit={unit >= 0 ? row[unit] : null}
            role={roles[index]}
          />
        </div>
      ))}
    </dl>
  )
}

/** One no-wrap measurement with a strong figure and a quiet measurement unit. */
function Reading({
  value,
  unit,
  role,
}: {
  value: unknown
  unit: unknown
  role: string | null
}) {
  const parts = reading(value, unit)
  return (
    <dd className="mt-0.5 min-w-0">
      <span className="inline-flex max-w-full items-baseline whitespace-nowrap font-mono tabular-nums">
        <span
          className={`truncate text-[1.05rem] font-semibold tracking-[-0.01em] ${
            role === null ? "text-foreground" : ""
          }`}
          style={role === null ? undefined : { color: colorFor(role) }}
        >
          {parts.value}
        </span>
        {parts.unit !== "" && (
          <span
            className={`shrink-0 font-sans text-meta font-normal text-muted-foreground ${
              parts.unit === "%" ? "" : "ml-1"
            }`}
          >
            {parts.unit}
          </span>
        )}
      </span>
    </dd>
  )
}

/** A tile's value: a number formatted, a label kept, and nothing invented. */
function reading(value: unknown, unit: unknown): { value: string; unit: string } {
  if (typeof value === "number" && Number.isFinite(value)) {
    return formatMeasureParts(value, unit)
  }
  return {
    value: typeof value === "string" && value !== "" ? value : "—",
    unit: typeof unit === "string" && unit !== "" ? formatUnit(unit) : "",
  }
}
