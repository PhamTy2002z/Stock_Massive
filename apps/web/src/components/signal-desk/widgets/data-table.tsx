"use client"

/**
 * The numbers, plainly — and the one widget every viewer is required to have.
 *
 * It is both a widget a Study may choose and the route every other widget
 * degrades to: a name this build does not know, a version it has never heard
 * of, a frame whose kind the chosen widget cannot draw. That is why it accepts
 * every frame kind, and why it is the simplest thing in this directory. The
 * degradation has to be the one path that cannot itself fail.
 *
 * Wide frames scroll inside their own box rather than pushing the panel — a
 * heatmap has seventeen columns and the inspector is four hundred pixels wide.
 * Tall ones scroll in the same box for the same reason, and the header sticks
 * to the top of it: a frame is not bounded by anything on the wire, and a
 * screener that answered with four hundred rows would otherwise push the
 * provenance strip and every block under it off a panel that does not scroll
 * as a page. The rows are *not* truncated to achieve that — this is the one
 * surface that has to be able to show every number a Study produced, so the
 * box is bounded and the numbers are not.
 * The table sizes to its own content (`w-max`) rather than to the box, because
 * a table told to be the box's width squeezes seventeen columns into four
 * hundred pixels and clips them where nothing indicates a clip. And the box is
 * a focusable region with a name, because a scroll area a reader can only reach
 * by dragging is a scroll area a keyboard cannot reach at all.
 *
 * **The columns sort, and that is not a chart feature.** This is the surface a
 * reader falls back to when the picture is unavailable, and the first thing
 * anybody does with a fallback table is look for the largest row. Sorting is
 * client-side and reversible and changes no number; the frame's own order is
 * always one more click away, because that order is what the Study chose.
 */

import { useMemo, useState } from "react"

import { ArrowDown, ArrowUp } from "lucide-react"

import {
  axisPresentation,
  formatMeasureParts,
  formatUnit,
  labelOf,
  type AxisPresentation,
} from "../frame"
import type { WidgetProps } from "../widget-registry"

type Direction = "asc" | "desc"

export function DataTableWidget({ frame }: WidgetProps) {
  const [sort, setSort] = useState<{ column: number; direction: Direction } | null>(
    null,
  )

  const rows = useMemo(() => {
    if (sort === null) return frame.rows
    const ordered = [...frame.rows]
    // The direction is applied inside the comparison rather than by reversing
    // the result: a missing cell sorts last either way, and a reversal would
    // float every hole to the top of a descending column.
    ordered.sort((left, right) =>
      compare(left[sort.column], right[sort.column], sort.direction),
    )
    return ordered
  }, [frame.rows, sort])
  const columns = frame.columns.map((column, position) =>
    columnFormatting(frame, column, position),
  )

  if (frame.rows.length === 0) {
    return (
      <p className="text-meta text-muted-foreground">Không có dòng dữ liệu nào.</p>
    )
  }

  return (
    <div
      role="region"
      aria-label={`Bảng số liệu, ${frame.rows.length} dòng, ${frame.columns.length} cột, cuộn được`}
      tabIndex={0}
      className="max-h-[26rem] overflow-auto rounded-sm scrollbar-thin focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      <table className="w-max min-w-full border-collapse text-meta">
        {/* The header is opaque because it is sticky: rows scroll *under* it,
            and a transparent cell would let them through. The tone is the
            ground's own — every route to this table renders it in the desk
            panel, which paints `bg-background` — so the band reads as the
            surface holding still rather than as a card that was not there
            before.

            The hairline travels with the header rather than with the row,
            because a border on a `sticky` cell scrolls away from it in every
            engine — the rule has to be drawn as the cell's own edge. */}
        <thead className="[&_th]:border-b [&_th]:border-border">
          <tr>
            {frame.columns.map((column, position) => {
              const active = sort?.column === position
              const numeric = columns[position].numeric
              return (
                <th
                  key={column}
                  scope="col"
                  aria-sort={
                    active
                      ? sort.direction === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                  className={`sticky top-0 z-10 whitespace-nowrap bg-background px-2 py-1.5 font-medium text-muted-foreground ${
                    numeric ? "text-right" : "text-left"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSort(next(sort, position))}
                    className={`inline-flex w-full items-center gap-1 hover:text-ink-2 ${
                      numeric ? "justify-end" : "justify-start"
                    }`}
                  >
                    <span className={numeric ? "text-right" : "text-left"}>
                      <span className="block">{labelOf(frame, column)}</span>
                      {columns[position].presentation?.unit && (
                        <span className="block font-mono text-micro font-normal tabular-nums text-ink-6">
                          {columns[position].presentation.unit}
                        </span>
                      )}
                    </span>
                    {active &&
                      (sort.direction === "asc" ? (
                        <ArrowUp className="size-3" aria-hidden />
                      ) : (
                        <ArrowDown className="size-3" aria-hidden />
                      ))}
                  </button>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-hairline last:border-0">
              {frame.columns.map((column, position) => (
                <td
                  key={column}
                  className={`whitespace-nowrap px-2 py-1.5 ${
                    columns[position].numeric
                      ? "text-right font-mono tabular-nums"
                      : "text-left"
                  }`}
                >
                  {cell(frame, row, position, columns[position].presentation)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * The next state of one column's sort: ascending, descending, then back.
 *
 * The third press restores the frame's own order rather than cycling between
 * two — the order the Study chose is a claim about the numbers, and a table
 * with no way back to it is a table that has quietly replaced it.
 */
function next(
  current: { column: number; direction: Direction } | null,
  column: number,
): { column: number; direction: Direction } | null {
  if (current === null || current.column !== column) return { column, direction: "asc" }
  if (current.direction === "asc") return { column, direction: "desc" }
  return null
}

/** Numbers compared as numbers, text collated, and a missing cell always last. */
function compare(left: unknown, right: unknown, direction: Direction): number {
  const leftMissing = left === null || left === undefined
  const rightMissing = right === null || right === undefined
  if (leftMissing || rightMissing) {
    return leftMissing === rightMissing ? 0 : leftMissing ? 1 : -1
  }
  const order =
    typeof left === "number" && typeof right === "number"
      ? left - right
      : String(left).localeCompare(String(right), "vi")
  return direction === "asc" ? order : -order
}

/**
 * One cell, with the difference between nothing and zero kept.
 *
 * A missing bucket prints an em dash. Writing `0` would be a different and
 * false claim: that the quarter hour existed and nobody traded in it.
 */
function cell(
  frame: WidgetProps["frame"],
  row: unknown[],
  position: number,
  presentation: AxisPresentation | null,
): string {
  const value = row[position]
  const unitAt = frame.columns.indexOf("unit")
  const valueAt = frame.columns.indexOf("value")

  if (position === unitAt) {
    const measured = valueAt >= 0 ? row[valueAt] : null
    if (typeof measured === "number" && Number.isFinite(measured)) {
      return formatMeasureParts(measured, value).unit || "—"
    }
    return typeof value === "string" && value !== "" ? formatUnit(value) : "—"
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    if (position === valueAt && unitAt >= 0) {
      return formatMeasureParts(value, row[unitAt]).value
    }
    return presentation?.format(value) ?? axisPresentation([value], null).format(value)
  }
  if (typeof value === "string" && value !== "") return value
  return "—"
}

interface ColumnFormatting {
  numeric: boolean
  presentation: AxisPresentation | null
}

/** One scale and one alignment for every comparable value in a column. */
function columnFormatting(
  frame: WidgetProps["frame"],
  column: string,
  position: number,
): ColumnFormatting {
  const values = frame.rows.flatMap((row) => {
    const value = row[position]
    return typeof value === "number" && Number.isFinite(value) ? [value] : []
  })
  if (values.length === 0) return { numeric: false, presentation: null }

  // A row-level unit belongs in the adjacent unit column. Its value column is
  // still right-aligned, but cannot have one shared scale because the rows may
  // mix percentages, currency, counts and ratios.
  if (column === "value" && frame.columns.includes("unit")) {
    return { numeric: true, presentation: null }
  }

  const label = labelOf(frame, column)
  const isStoredShare = /(^|_)share($|_)/i.test(column) && !/_pct$/i.test(column)
  const isPercentPoint =
    /(^|_)(pct|percentile)($|_)/i.test(column) || label.includes("(%)")
  const isCurrency = /(^|_)vnd($|_)/i.test(column)
  const isCount = /rank|count|frequency|sessions?/i.test(column)
  const isAmount = /amount|volume|close|price|low|high|current|zone/i.test(column)

  if (isStoredShare) {
    return { numeric: true, presentation: axisPresentation(values, "%", "percent") }
  }
  if (frame.unit === "share" && !isCount && !isAmount) {
    return { numeric: true, presentation: axisPresentation(values, "%", "percent") }
  }
  if (isPercentPoint) {
    return { numeric: true, presentation: axisPresentation(values, "%") }
  }
  if (isCurrency || (formatUnit(frame.unit ?? "") === "đồng" && !isCount)) {
    return { numeric: true, presentation: axisPresentation(values, "VND") }
  }
  if (isAmount && frame.unit) {
    return { numeric: true, presentation: axisPresentation(values, frame.unit) }
  }
  return { numeric: true, presentation: axisPresentation(values, null) }
}
