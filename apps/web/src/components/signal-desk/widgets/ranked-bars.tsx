"use client"

/**
 * A ranking: longest on top, labelled on the left, valued at its own end.
 *
 * Horizontal rather than vertical because the labels are words — a bucket, a
 * ticker, a phase of the session — and vertical bars would either rotate them
 * or clip them. The order is the frame's own: the Study ranked the rows, and
 * re-sorting here would be this layer deciding what "top" means.
 *
 * **No value axis.** A ranking read left to right along a bottom axis asks the
 * reader to trace a bar back down to a scale, while `bar_series` puts its scale
 * on the left; two conventions on one panel is one too many. The number sits at
 * the end of its own bar instead, which is where the eye already is.
 *
 * **The leader carries the focus, and nothing else does.** It is the row the
 * ranking exists to name.
 */

import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { columnIndex, formatValue, labelOf, numberAt, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { AXIS, FOCUS, SERIES, TOOLTIP_STYLE } from "./chart-theme"

/** How many rows a ranking shows. Beyond this it is a table, not a ranking. */
const MAX_ROWS = 8

/** Room at the right for the value printed at the end of the longest bar. */
const VALUE_GUTTER = 56

export function RankedBarsWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const valueColumn =
    typeof options.value === "string" ? options.value : frame.columns[1]
  const label = columnIndex(frame, labelColumn)
  const value = columnIndex(frame, valueColumn)

  const ranked = frame.rows
    .map((row) => ({ label: textAt(row, label), value: numberAt(row, value) }))
    .filter((point): point is { label: string; value: number } => point.value !== null)

  const data = ranked.slice(0, MAX_ROWS)
  const hidden = ranked.length - data.length

  if (data.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có hạng nào để xếp.</p>
  }

  return (
    <figure className="m-0">
      <div
        style={{ height: Math.max(96, data.length * 26 + 8) }}
        className="w-full"
        role="img"
        aria-label={`Xếp hạng theo ${labelOf(frame, valueColumn ?? "")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: VALUE_GUTTER, bottom: 0, left: 0 }}
          >
            {/* Hidden rather than absent: the scale is still what places the
                bars, it is simply not a second thing to read. */}
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="label" {...AXIS} width={64} />
            <Tooltip
              {...TOOLTIP_STYLE}
              // Recharts types a tooltip value as anything a data key may hold,
              // so the narrowing happens here rather than in the signature.
              formatter={(entry: unknown) => [
                formatValue(typeof entry === "number" ? entry : 0, options.valueFormat),
                labelOf(frame, valueColumn ?? ""),
              ]}
            />
            <Bar dataKey="value" radius={[0, 2, 2, 0]}>
              {/* The top row, by the Study's own order rather than by whose
                  value is largest: the Study ranked these, and a tie at the top
                  is still one leader — two accented bars spend the mark. */}
              {data.map((point, index) => (
                <Cell key={point.label} fill={index === 0 ? FOCUS : SERIES} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                fill="hsl(var(--widget-axis))"
                fontSize={11}
                formatter={(entry: unknown) =>
                  formatValue(typeof entry === "number" ? entry : 0, options.valueFormat)
                }
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {hidden > 0 && (
        <figcaption className="mt-1.5 text-meta text-muted-foreground">
          Còn {hidden} mục ngoài top {MAX_ROWS} — xem đầy đủ ở dạng bảng.
        </figcaption>
      )}
    </figure>
  )
}
