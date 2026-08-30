"use client"

/**
 * How a total got from where it started to where it ended, one step at a time.
 *
 * The bars float: each one begins where the last ended, so the picture is the
 * running balance rather than a row of independent quantities. Recharts has no
 * floating bar, so the base is a transparent bar stacked under the visible one —
 * which is arithmetic, and arithmetic is what the test on this file checks
 * rather than the rendering.
 *
 * **Direction is measured, not declared.** A step that adds is `up` and one that
 * subtracts is `down`, read off the sign of the step itself. That is the one
 * place in this directory where the browser assigns a role, and it is legitimate
 * because it is not a claim about the market: it is the sign of a number that is
 * already on the page.
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
import { AXIS, colorFor, GRID, TOOLTIP_STYLE } from "./chart-theme"

export interface Step {
  label: string
  base: number
  step: number
  total: number
}

/**
 * The running balance behind each bar.
 *
 * Exported so the sums are testable without a renderer: a chart whose numbers
 * are only checked by looking at it is a chart nobody checked.
 */
export function steps(labels: string[], values: (number | null)[]): Step[] {
  let running = 0
  const out: Step[] = []
  for (let index = 0; index < labels.length; index += 1) {
    const step = values[index]
    if (step === null || step === undefined) continue
    const base = running
    running += step
    out.push({ label: labels[index], base, step, total: running })
  }
  return out
}

export function WaterfallWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const valueColumn =
    typeof options.value === "string" ? options.value : frame.columns[1]
  const label = columnIndex(frame, labelColumn)
  const value = columnIndex(frame, valueColumn)

  const built = steps(
    frame.rows.map((row) => textAt(row, label)),
    frame.rows.map((row) => numberAt(row, value)),
  )

  if (built.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có bước nào để cộng dồn.</p>
  }

  const axis = axisPresentation(
    built.flatMap((entry) => [entry.base, entry.total]),
    frame.unit,
    options.valueFormat,
  )

  return (
    <figure className="m-0">
      <p className="mb-1 text-meta text-muted-foreground">{axis.unit}</p>
      <div
        style={{ height: 200 }}
        className="w-full"
        role="img"
        aria-label={`Cộng dồn ${labelOf(frame, valueColumn ?? "")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={built} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis {...AXIS} tickFormatter={axis.format} width={44} />
            <Tooltip
              {...TOOLTIP_STYLE}
              formatter={(_value: unknown, _name: unknown, item: unknown) => {
                const entry = (item as { payload?: Step })?.payload
                if (entry === undefined) return ["—", ""]
                return [axis.measure(entry.step), `Còn lại ${axis.measure(entry.total)}`]
              }}
            />
            {/* The invisible plinth each visible bar stands on. */}
            <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="step" stackId="w" radius={[2, 2, 0, 0]} isAnimationActive={false}>
              {built.map((entry) => (
                <Cell
                  key={entry.label}
                  fill={colorFor(entry.step >= 0 ? "up" : "down")}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
