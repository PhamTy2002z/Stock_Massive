"use client"

/**
 * A ranking: longest on top, labelled on the left.
 *
 * Horizontal rather than vertical because the labels are words — a bucket, a
 * ticker, a phase of the session — and vertical bars would either rotate them
 * or clip them. The order is the frame's own: the Study ranked the rows, and
 * re-sorting here would be this layer deciding what "top" means.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { columnIndex, formatValue, labelOf, numberAt, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { AXIS, GRID, TOOLTIP_STYLE } from "./chart-theme"

/** How many rows a ranking shows. Beyond this it is a table, not a ranking. */
const MAX_ROWS = 8

export function RankedBarsWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const valueColumn =
    typeof options.value === "string" ? options.value : frame.columns[1]
  const label = columnIndex(frame, labelColumn)
  const value = columnIndex(frame, valueColumn)

  const data = frame.rows
    .map((row) => ({ label: textAt(row, label), value: numberAt(row, value) }))
    .filter((point) => point.value !== null)
    .slice(0, MAX_ROWS)

  if (data.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có hạng nào để xếp.</p>
  }

  return (
    <div
      style={{ height: Math.max(96, data.length * 26 + 24) }}
      className="w-full"
      role="img"
      aria-label={`Xếp hạng theo ${labelOf(frame, valueColumn ?? "")}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
        >
          <CartesianGrid {...GRID} vertical horizontal={false} />
          <XAxis
            type="number"
            {...AXIS}
            tickFormatter={(entry: number) => formatValue(entry, options.valueFormat)}
          />
          <YAxis type="category" dataKey="label" {...AXIS} width={56} />
          <Tooltip
            {...TOOLTIP_STYLE}
            // Recharts types a tooltip value as anything a data key may hold,
            // so the narrowing happens here rather than in the signature.
            formatter={(entry: unknown) => [
              formatValue(typeof entry === "number" ? entry : 0, options.valueFormat),
              labelOf(frame, valueColumn ?? ""),
            ]}
          />
          <Bar dataKey="value" fill="hsl(var(--chart-3))" radius={[0, 2, 2, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
