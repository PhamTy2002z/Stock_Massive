"use client"

/**
 * A bar per bucket, along whatever axis the Study said runs left to right.
 *
 * Recharts, because the axis, the ticks and the tooltip are the parts nobody
 * should be hand-rolling twice. What is not left to it is *colour*: the fills
 * come from `--chart-1`, which is defined for both themes, so the chart is
 * legible on the dark ground the app opens on and on paper. A hard-coded hex
 * would be right in exactly one of them.
 *
 * The container measures its parent rather than taking a width, because the
 * inspector is a panel a reader drags. During a drag the panel freezes its own
 * width (`canvas-panel.tsx`), so this re-measures once on release instead of on
 * every pointer move.
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

export function BarSeriesWidget({ frame, options }: WidgetProps) {
  const xColumn = typeof options.x === "string" ? options.x : frame.columns[0]
  const yColumn = typeof options.y === "string" ? options.y : frame.columns[1]
  const x = columnIndex(frame, xColumn)
  const y = columnIndex(frame, yColumn)

  const data = frame.rows
    .map((row) => ({ label: textAt(row, x), value: numberAt(row, y) }))
    // A bucket with no value is dropped rather than plotted at zero: a bar of
    // height nothing says "nobody traded", and an absent bucket says the
    // exchange has no such quarter hour. Only one of those is about the company.
    .filter((point) => point.value !== null)

  if (data.length === 0) {
    return (
      <p className="text-meta text-muted-foreground">
        Không có điểm dữ liệu nào để vẽ.
      </p>
    )
  }

  return (
    <div className="h-52 w-full" role="img" aria-label={chartLabel(frame, yColumn)}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" />
          <YAxis
            {...AXIS}
            width={52}
            tickFormatter={(value: number) => formatValue(value, options.yFormat)}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            // Recharts types a tooltip value as anything a data key may hold,
            // so the narrowing happens here rather than in the signature.
            formatter={(value: unknown) => [
              formatValue(typeof value === "number" ? value : 0, options.yFormat),
              labelOf(frame, yColumn ?? ""),
            ]}
          />
          <Bar dataKey="value" fill="hsl(var(--chart-1))" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * What a screen reader is told this picture is.
 *
 * The chart itself is a grid of rectangles with no text in it, so without this
 * the block announces nothing at all. The same numbers are reachable as a table
 * through the panel's fallback, which is the other half of the answer.
 */
function chartLabel(frame: WidgetProps["frame"], column: string | undefined): string {
  return `Biểu đồ cột: ${labelOf(frame, column ?? "")}`
}
