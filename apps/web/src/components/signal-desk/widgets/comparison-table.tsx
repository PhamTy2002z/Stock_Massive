"use client"

/**
 * Rows are the things being compared; columns are what they are compared on.
 *
 * A table rather than a chart, and it earns its place beside one: bars show the
 * gap and a table is where somebody checks a figure before acting on it. The
 * server puts both on a comparison because neither does the other's job.
 *
 * **The winner mark is per cell, and that is the whole reason this widget
 * exists.** A comparison's claim is that *this* symbol wins on *this* metric —
 * not that a row wins, which is a sentence about a company nobody measured. So
 * the colour comes off `cellRoles` and never off the row or the column.
 *
 * **No sorting.** The order is the frame's, and re-sorting here would be this
 * layer deciding what "best" means across metrics that do not share a direction.
 *
 * The whole thing scrolls sideways inside its own box rather than widening the
 * panel, because the panel is a column a reader drags and a table that pushed
 * it wider would push the answer off the screen.
 */

import { cellRole, columnIndex, formatMeasure, labelOf, numberAt, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { cellColorFor } from "./chart-theme"

export function ComparisonTableWidget({ frame, options }: WidgetProps) {
  const entityColumn =
    typeof options.entity === "string" ? options.entity : frame.columns[0]
  const metricNames = Array.isArray(options.metrics)
    ? options.metrics.filter((name): name is string => typeof name === "string")
    : frame.columns.slice(1)

  const entity = columnIndex(frame, entityColumn)
  const metrics = metricNames
    .map((name) => ({ name, index: columnIndex(frame, name) }))
    .filter((metric) => metric.index >= 0)

  if (metrics.length === 0 || frame.rows.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có gì để đối chiếu.</p>
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-hairline">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr className="border-b border-hairline bg-surface-sunken">
            <th
              scope="col"
              className="px-3 py-2 text-left text-meta font-medium text-muted-foreground"
            >
              {labelOf(frame, entityColumn ?? "")}
            </th>
            {metrics.map((metric) => (
              <th
                key={metric.name}
                scope="col"
                className="px-3 py-2 text-right text-meta font-medium text-muted-foreground"
              >
                {labelOf(frame, metric.name)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {frame.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-hairline last:border-b-0">
              <th
                scope="row"
                className="px-3 py-2 text-left font-medium text-foreground"
              >
                {textAt(row, entity)}
              </th>
              {metrics.map((metric) => {
                const role = cellRole(frame, rowIndex, metric.name)
                const colour = cellColorFor(role)
                const value = numberAt(row, metric.index)
                return (
                  <td
                    key={metric.name}
                    className="px-3 py-2 text-right font-mono tabular-nums"
                    style={colour === null ? undefined : { color: colour }}
                    // Said in words as well as in colour: a reader who cannot
                    // separate the two hues still learns which cell won.
                    title={role === null ? undefined : role}
                  >
                    {value === null ? "—" : formatMeasure(value, frame.unit)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
