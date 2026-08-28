"use client"

/**
 * A bar per bucket, along whatever axis the Study said runs left to right.
 *
 * Recharts, because the axis, the ticks and the tooltip are the parts nobody
 * should be hand-rolling twice. What is not left to it is *colour*: the bars
 * come from the shared neutral series token, and exactly one bar — the peak —
 * carries the focus. A whole series in the focus colour spends the only mark
 * that means "this one is the answer".
 *
 * **The ceiling is derived, because the true maximum says nothing.** A
 * liquidity profile is one dominant bucket and thirty small ones; scaled to the
 * dominant bucket the thirty are a rule along the baseline, and the chart
 * repeats the headline instead of adding to it. See {@link plotCeiling}.
 *
 * The container measures its parent rather than taking a width, because the
 * inspector is a panel a reader drags. During a drag the panel freezes its own
 * width (`signal-desk-panel.tsx`), so this re-measures once on release instead of on
 * every pointer move.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { axisPresentation, columnIndex, labelOf, numberAt, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { ChartHeading } from "./chart-heading"
import { AXIS, FOCUS, GRID, SERIES, TOOLTIP_STYLE } from "./chart-theme"

/** Which bar is the tallest *ordinary* one, and the room left above it. */
const PERCENTILE = 0.9
const HEADROOM = 1.15

/**
 * How far up the plot goes, or `null` for "let the chart scale itself".
 *
 * The ninetieth percentile with a little headroom, capped at the true maximum.
 * Those two halves are the whole rule and each does one job: the percentile
 * ignores an outlier so the tail is a comparison rather than a baseline, and
 * the `min` means a flat series is never capped at all — in a flat series the
 * percentile already *is* the maximum, so the ceiling comes back as the
 * maximum and nothing is clipped.
 *
 * A series that crosses zero gets `null`. A ceiling on a chart with negative
 * bars would truncate one end of a comparison the reader is making across the
 * axis, which is a different chart from the one the Study asked for.
 */
export function plotCeiling(values: number[]): number | null {
  if (values.length === 0 || values.some((value) => value < 0)) return null

  const largest = Math.max(...values)
  const sorted = [...values].sort((left, right) => left - right)
  const at = PERCENTILE * (sorted.length - 1)
  const below = sorted[Math.floor(at)]
  const above = sorted[Math.ceil(at)]
  const percentile = below + (above - below) * (at - Math.floor(at))

  const ceiling = Math.min(largest, percentile * HEADROOM)
  // Every bar at nought is a chart with no height to divide; recharts scales
  // that better than a domain of `[0, 0]` does.
  return ceiling > 0 ? ceiling : null
}

export function BarSeriesWidget({ frame, options }: WidgetProps) {
  const xColumn = typeof options.x === "string" ? options.x : frame.columns[0]
  const yColumn = typeof options.y === "string" ? options.y : frame.columns[1]
  const x = columnIndex(frame, xColumn)
  const y = columnIndex(frame, yColumn)

  const points = frame.rows
    .map((row) => ({ label: textAt(row, x), value: numberAt(row, y) }))
    // A bucket with no value is dropped rather than plotted at zero: a bar of
    // height nothing says "nobody traded", and an absent bucket says the
    // exchange has no such quarter hour. Only one of those is about the company.
    .filter((point): point is { label: string; value: number } => point.value !== null)

  if (points.length === 0) {
    return (
      <p className="text-meta text-muted-foreground">
        Không có điểm dữ liệu nào để vẽ.
      </p>
    )
  }

  const values = points.map((point) => point.value)
  const yAxis = axisPresentation(values, frame.unit, options.yFormat)
  const ceiling = plotCeiling(values)
  const over = ceiling === null ? [] : points.filter((point) => point.value > ceiling)
  // The first bar to reach the maximum, not every bar that equals it: a series
  // where every bucket is the same has no peak, and painting all of them in the
  // focus colour would be the whole series wearing the mark that means "this
  // one is the answer".
  const peak = values.indexOf(Math.max(...values))
  // Drawn at the ceiling rather than through it: recharts would happily paint a
  // bar past the top of its own plot, and a bar overlapping the block above is
  // a chart that has escaped its box.
  const data = points.map((point, index) => ({
    ...point,
    plotted: ceiling === null ? point.value : Math.min(point.value, ceiling),
    focused: index === peak || (ceiling !== null && point.value > ceiling),
  }))

  return (
    <figure className="m-0">
      <ChartHeading label={labelOf(frame, yColumn ?? "")} unit={yAxis.unit} />
      <div
        className="h-52 w-full"
        role="img"
        aria-label={`${chartLabel(frame, yColumn)}, đơn vị ${
          yAxis.unit || "theo số liệu gốc"
        }`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" />
            <YAxis
              {...AXIS}
              width={48}
              domain={ceiling === null ? undefined : [0, ceiling]}
              tickFormatter={yAxis.format}
            />
            <Tooltip
              {...TOOLTIP_STYLE}
              // The bar is drawn from `plotted` and read from `value`: a capped
              // bar has to say its own number, or the cap becomes a number the
              // reader cannot get back.
              formatter={(_drawn: unknown, _key: unknown, item: unknown) => [
                yAxis.measure(measured(item)),
                labelOf(frame, yColumn ?? ""),
              ]}
            />
            <Bar dataKey="plotted" radius={[2, 2, 0, 0]}>
              {data.map((point) => (
                <Cell key={point.label} fill={point.focused ? FOCUS : SERIES} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {over.length > 0 && ceiling !== null && (
        <figcaption className="mt-1.5 text-pretty text-meta text-muted-foreground">
          Trục dừng ở {yAxis.measure(ceiling)} để các cột nhỏ so được với nhau. {over.length}{" "}
          cột cao hơn mức này được tô màu nhấn và cắt tại đó — số thật nằm trong
          bảng.
        </figcaption>
      )}
    </figure>
  )
}

/** The true value behind a tooltip's datum, whatever recharts hands over. */
function measured(item: unknown): number {
  if (typeof item !== "object" || item === null) return 0
  const payload = (item as { payload?: unknown }).payload
  if (typeof payload !== "object" || payload === null) return 0
  const value = (payload as { value?: unknown }).value
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

/**
 * What a screen reader is told this picture is.
 *
 * The chart itself is a grid of rectangles with no text in it, so without this
 * the block announces nothing at all. The same numbers are reachable as a table
 * from the disclosure the block draws under every widget, which is the other
 * half of the answer.
 */
function chartLabel(frame: WidgetProps["frame"], column: string | undefined): string {
  return `Biểu đồ cột: ${labelOf(frame, column ?? "")}`
}
