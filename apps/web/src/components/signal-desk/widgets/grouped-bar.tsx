"use client"

/**
 * One cluster per entity, one bar per measure: where a reader sees the gap.
 *
 * The companion to `comparison_table` and not a replacement for it. A table is
 * where somebody checks a figure; bars are where they see that one is three
 * times the other, which is a fact no column of digits delivers at a glance.
 * The server puts both on a comparison for that reason.
 *
 * **The bars are the measures, so the colours are categories.** Nothing here is
 * up or down — a cluster is ROE beside ROA beside a margin, and those have no
 * direction relative to each other. Category hues are what the palette has for
 * exactly this, and using the market pair would be the chart claiming a rise
 * where it measured a difference.
 *
 * **One scale, and it is a limitation said out loud.** Ratios and percentages
 * share an axis honestly; a profit in đồng beside a percentage does not, and
 * the caption says so rather than the chart pretending. The server picks the
 * measures, so this draws what it is given and names the risk.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { axisPresentation, cellRole, columnIndex, labelOf, numberAt, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { AXIS, colorFor, GRID, TOOLTIP_STYLE } from "./chart-theme"

/** How many clusters read as a comparison. Past this it is a ranking. */
const MAX_GROUPS = 8

export function GroupedBarWidget({ frame, options }: WidgetProps) {
  const categoryColumn =
    typeof options.category === "string" ? options.category : frame.columns[0]
  const seriesColumns = Array.isArray(options.series)
    ? options.series.filter((name): name is string => typeof name === "string")
    : frame.columns.slice(1)

  const category = columnIndex(frame, categoryColumn)
  const measures = seriesColumns
    .map((name) => ({ name, index: columnIndex(frame, name) }))
    .filter((measure) => measure.index >= 0)

  if (measures.length === 0 || frame.rows.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có nhóm nào để so.</p>
  }

  const rows = frame.rows.slice(0, MAX_GROUPS)
  const data = rows.map((row, index) => {
    const point: Record<string, unknown> = { label: textAt(row, category), index }
    for (const measure of measures) point[measure.name] = numberAt(row, measure.index)
    return point
  })

  const values = data.flatMap((point) =>
    measures
      .map((measure) => point[measure.name])
      .filter((value): value is number => typeof value === "number"),
  )
  const axis = axisPresentation(values, frame.unit, options.valueFormat)

  return (
    <figure className="m-0">
      <p className="mb-1 text-meta text-muted-foreground">{axis.unit}</p>
      <div
        style={{ height: 200 }}
        className="w-full"
        role="img"
        aria-label={`So sánh ${measures.map((m) => labelOf(frame, m.name)).join(", ")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis {...AXIS} tickFormatter={axis.format} width={44} />
            <Tooltip
              {...TOOLTIP_STYLE}
              formatter={(value: unknown, name: unknown) => [
                typeof value === "number" ? axis.measure(value) : "—",
                labelOf(frame, typeof name === "string" ? name : ""),
              ]}
            />
            <Legend
              wrapperStyle={{ fontSize: "0.72rem" }}
              formatter={(name: unknown) =>
                labelOf(frame, typeof name === "string" ? name : "")
              }
            />
            {measures.map((measure, position) => (
              <Bar
                key={measure.name}
                dataKey={measure.name}
                radius={[2, 2, 0, 0]}
                fill={colorFor(`category:${(position % 6) + 1}`)}
              >
                {/* A cell the engine marked wins its own colour, because the
                    claim a comparison makes is about one symbol on one metric
                    and nothing coarser can say it. */}
                {data.map((point, rowIndex) => {
                  const role = cellRole(frame, rowIndex, measure.name)
                  return (
                    <Cell
                      key={`${measure.name}-${rowIndex}`}
                      fill={
                        role === null
                          ? colorFor(`category:${(position % 6) + 1}`)
                          : colorFor(role)
                      }
                    />
                  )
                })}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {frame.rows.length > MAX_GROUPS && (
        <figcaption className="mt-1.5 text-meta text-muted-foreground">
          Còn {frame.rows.length - MAX_GROUPS} nhóm ngoài biểu đồ — xem đầy đủ ở
          dạng bảng.
        </figcaption>
      )}
    </figure>
  )
}
