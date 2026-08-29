"use client"

/**
 * Two quantities against each other, and the lines that make the four corners
 * mean something.
 *
 * A scatter without reference lines is a cloud: a reader can see that points
 * differ and not what any of them is *on the far side of*. The medians of what
 * is actually plotted are drawn as the two dividers, so the quadrants read as
 * "above typical on both", "cheap and strong", and so on — a comparison within
 * this sample rather than against a number invented here.
 *
 * Medians rather than means for the reason percentile floors exist elsewhere in
 * this system: one extraordinary point drags a mean across the panel and takes
 * every label with it.
 */

import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts"

import {
  columnIndex,
  formatNumber,
  labelOf,
  numberAt,
  pointRole,
  textAt,
} from "../frame"
import type { WidgetProps } from "../widget-registry"
import { AXIS, colorFor, GRID, resolveRoles, SERIES, TOOLTIP_STYLE } from "./chart-theme"

/** The two dividers: present enough to read a quadrant by, quiet enough not to
    compete with the points that sit on them. */
const DIVIDER = "hsl(var(--widget-axis) / 0.45)"

export function ScatterQuadrantWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const xColumn = typeof options.x === "string" ? options.x : frame.columns[1]
  const yColumn = typeof options.y === "string" ? options.y : frame.columns[2]

  const label = columnIndex(frame, labelColumn)
  const x = columnIndex(frame, xColumn)
  const y = columnIndex(frame, yColumn)

  const points = frame.rows
    .map((row, index) => ({
      label: textAt(row, label),
      x: numberAt(row, x),
      y: numberAt(row, y),
      role: pointRole(frame, index),
    }))
    // Both coordinates or neither: a point with one is not somewhere on the
    // plane, and plotting it at zero would put it in a quadrant it is not in.
    .filter(
      (point): point is {
        label: string
        x: number
        y: number
        role: string | null
      } => point.x !== null && point.y !== null,
    )

  if (points.length === 0) {
    return (
      <p className="text-meta text-muted-foreground">
        Không có điểm nào có đủ hai toạ độ.
      </p>
    )
  }

  const midX = median(points.map((point) => point.x))
  const midY = median(points.map((point) => point.y))
  const { roles } = resolveRoles(points.map((point) => point.role))

  return (
    <div
      className="h-56 w-full"
      role="img"
      aria-label={`Biểu đồ phân tán: ${labelOf(frame, xColumn ?? "")} và ${labelOf(
        frame,
        yColumn ?? "",
      )}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
          <CartesianGrid {...GRID} vertical />
          <XAxis
            type="number"
            dataKey="x"
            name={labelOf(frame, xColumn ?? "")}
            {...AXIS}
            tickFormatter={(value: number) => formatNumber(value)}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={labelOf(frame, yColumn ?? "")}
            {...AXIS}
            width={52}
            tickFormatter={(value: number) => formatNumber(value)}
          />
          {/* Every point the same size: a third quantity encoded as area is a
              claim nothing here measured. */}
          <ZAxis range={[36, 36]} />
          <ReferenceLine x={midX} stroke={DIVIDER} strokeDasharray="3 3" />
          <ReferenceLine y={midY} stroke={DIVIDER} strokeDasharray="3 3" />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(value: unknown) =>
              formatNumber(typeof value === "number" ? value : 0)
            }
            labelFormatter={() => ""}
          />
          {/* Every point the same colour unless the frame said otherwise.
              Nothing here is "the answer" — the reading is which quadrant a
              point is in, and a point this layer picked out would be it naming
              one. The engine that measured them may name one; this may not. */}
          <Scatter data={points} fill={SERIES}>
            {points.map((point, index) => (
              <Cell key={point.label} fill={colorFor(roles[index])} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

/** The middle value of what is plotted, which is where the dividers go. */
function median(values: number[]): number {
  const sorted = [...values].sort((left, right) => left - right)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle]
}
