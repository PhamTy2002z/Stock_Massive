"use client"

/**
 * A line across sessions, and a second one on its own axis where there is one.
 *
 * A line rather than bars because what a gathered series is *about* is the
 * shape between the points: an RSI over sixty sessions is a path, and drawing
 * it as sixty separate columns asks the reader to reassemble it.
 *
 * **Two axes, and the second one is opt-in.** A ratio beside a price is two
 * quantities in two units, and forcing them onto one scale flattens whichever
 * is smaller into the axis. The server says which column is the second series;
 * absent one, this is a single line and no right-hand axis is drawn — an empty
 * axis is a claim that there is something to compare.
 *
 * **A refused point is a gap, not a zero.** A series carries `null` where the
 * store had no number for that session, and recharts draws a break in the line.
 * Joining across it would draw a trend nobody measured.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import {
  axisPresentation,
  columnIndex,
  columnRole,
  labelOf,
  numberAt,
  textAt,
} from "../frame"
import type { WidgetProps } from "../widget-registry"
import { ChartHeading } from "./chart-heading"
import {
  AXIS,
  colorFor,
  GRID,
  resolveRoles,
  SERIES,
  SERIES_MUTED,
  TOOLTIP_STYLE,
} from "./chart-theme"

export function LineSeriesWidget({ frame, options }: WidgetProps) {
  const xColumn = typeof options.x === "string" ? options.x : frame.columns[0]
  const yColumn = typeof options.y === "string" ? options.y : frame.columns[1]
  const secondColumn =
    typeof options.secondary === "string" ? options.secondary : undefined

  const x = columnIndex(frame, xColumn)
  const y = columnIndex(frame, yColumn)
  const second = columnIndex(frame, secondColumn)

  const data = frame.rows.map((row) => ({
    label: textAt(row, x),
    value: numberAt(row, y),
    second: numberAt(row, second),
  }))

  if (data.every((point) => point.value === null)) {
    return (
      <p className="text-meta text-muted-foreground">
        Không phiên nào trong cửa sổ này có số để vẽ.
      </p>
    )
  }

  const primaryAxis = axisPresentation(
    data.flatMap((point) => (point.value === null ? [] : [point.value])),
    frame.unit,
    options.yFormat,
  )
  const secondaryAxis = axisPresentation(
    data.flatMap((point) => (point.second === null ? [] : [point.second])),
    frame.unit,
    options.yFormat,
  )

  // The two lines are two whole series, so the meaning is declared per column.
  // Where nothing is declared they keep the pairing they have always had: the
  // reading in the series colour, its companion stepped back and dashed.
  const { roles } = resolveRoles([
    columnRole(frame, yColumn),
    columnRole(frame, secondColumn),
  ])
  const primaryStroke = roles[0] === null ? SERIES : colorFor(roles[0])
  const secondaryStroke = roles[1] === null ? SERIES_MUTED : colorFor(roles[1])

  return (
    <figure className="m-0">
      <ChartHeading
        label={labelOf(frame, yColumn ?? "")}
        unit={primaryAxis.unit}
        secondary={second >= 0 ? labelOf(frame, secondColumn ?? "") : undefined}
      />
      <div
        className="h-52 w-full"
        role="img"
        aria-label={`Biểu đồ đường: ${labelOf(frame, yColumn ?? "")}, đơn vị ${
          primaryAxis.unit || "theo số liệu gốc"
        }`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis
              dataKey="label"
              {...AXIS}
              interval="preserveStartEnd"
              minTickGap={24}
            />
            <YAxis
              yAxisId="left"
              {...AXIS}
              width={48}
              tickFormatter={primaryAxis.format}
            />
            {second >= 0 && (
              <YAxis
                yAxisId="right"
                orientation="right"
                {...AXIS}
                width={48}
                tickFormatter={secondaryAxis.format}
              />
            )}
            <Tooltip
              {...TOOLTIP_STYLE}
              formatter={(value: unknown, name: unknown) => [
                name === "second"
                  ? secondaryAxis.measure(typeof value === "number" ? value : 0)
                  : primaryAxis.measure(typeof value === "number" ? value : 0),
                name === "second"
                  ? labelOf(frame, secondColumn ?? "")
                  : labelOf(frame, yColumn ?? ""),
              ]}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="value"
              stroke={primaryStroke}
              strokeWidth={1.5}
              dot={false}
              // The break is the point: a session the store refused is a hole in
              // the line rather than a value of nought.
              connectNulls={false}
            />
            {second >= 0 && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="second"
                stroke={secondaryStroke}
                strokeWidth={1.5}
                // Dashed as well as paler. The second series is on its own axis
                // and a reader who cannot separate two hues would otherwise have
                // no way to tell which line belongs to which scale.
                strokeDasharray="4 3"
                dot={false}
                connectNulls={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
