"use client"

/**
 * Parts of one whole, at most five of them.
 *
 * Angle is a worse encoding than position for judging a quantity, which is why
 * the server sends more than five parts to a ranking instead. What a donut is
 * genuinely good at is the one thing bars are not: saying *this is a whole, and
 * these are its parts*. Five or fewer, and that reading survives.
 *
 * **The number is printed beside its own slice.** A reader comparing two wedges
 * by eye is doing the thing angles are bad at; the legend carries the figure so
 * they do not have to.
 */

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

import { columnIndex, formatValue, labelOf, numberAt, pointRole, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"
import { colorFor, resolveRoles, TOOLTIP_STYLE } from "./chart-theme"

/** Past this a donut is a legend a reader matches swatches against. */
const MAX_PARTS = 5

export function DonutWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const valueColumn =
    typeof options.value === "string" ? options.value : frame.columns[1]
  const label = columnIndex(frame, labelColumn)
  const value = columnIndex(frame, valueColumn)

  const parts = frame.rows
    .map((row, index) => ({
      label: textAt(row, label),
      value: numberAt(row, value),
      role: pointRole(frame, index),
    }))
    .filter(
      (part): part is { label: string; value: number; role: string | null } =>
        part.value !== null && part.value > 0,
    )
    .slice(0, MAX_PARTS)

  if (parts.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có phần nào để chia.</p>
  }

  const declared = parts.some((part) => part.role !== null)
  const { roles } = resolveRoles(parts.map((part) => part.role))

  return (
    <figure className="m-0">
      <div
        style={{ height: 200 }}
        className="w-full"
        role="img"
        aria-label={`Cơ cấu theo ${labelOf(frame, valueColumn ?? "")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={parts}
              dataKey="value"
              nameKey="label"
              innerRadius="55%"
              outerRadius="80%"
              paddingAngle={1}
              isAnimationActive={false}
            >
              {parts.map((part, index) => (
                <Cell
                  key={part.label}
                  fill={colorFor(
                    declared ? roles[index] : `category:${(index % 6) + 1}`,
                  )}
                />
              ))}
            </Pie>
            <Tooltip
              {...TOOLTIP_STYLE}
              formatter={(entry: unknown) =>
                formatValue(typeof entry === "number" ? entry : 0, options.valueFormat)
              }
            />
            <Legend
              wrapperStyle={{ fontSize: "0.72rem" }}
              formatter={(name: unknown, entry: unknown) => {
                const payload = (entry as { payload?: { value?: number } })?.payload
                const measured =
                  typeof payload?.value === "number"
                    ? ` · ${formatValue(payload.value, options.valueFormat)}`
                    : ""
                return `${typeof name === "string" ? name : ""}${measured}`
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
