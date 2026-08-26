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
 *
 * **The columns sort, and that is not a chart feature.** This is the surface a
 * reader falls back to when the picture is unavailable, and the first thing
 * anybody does with a fallback table is look for the largest row. Sorting is
 * client-side and reversible and changes no number; the frame's own order is
 * always one more click away, because that order is what the Study chose.
 */

import { useMemo, useState } from "react"

import { ArrowDown, ArrowUp } from "lucide-react"

import { formatNumber, labelOf } from "../frame"
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

  if (frame.rows.length === 0) {
    return (
      <p className="text-meta text-muted-foreground">Không có dòng dữ liệu nào.</p>
    )
  }

  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className="w-full border-collapse text-meta">
        <thead>
          <tr className="border-b border-border">
            {frame.columns.map((column, position) => {
              const active = sort?.column === position
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
                  className="whitespace-nowrap px-2 py-1.5 text-left font-medium text-muted-foreground"
                >
                  <button
                    type="button"
                    onClick={() => setSort(next(sort, position))}
                    className="inline-flex items-center gap-1 hover:text-ink-2"
                  >
                    {labelOf(frame, column)}
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
                <td key={column} className="whitespace-nowrap px-2 py-1.5 tabular-nums">
                  {cell(row[position])}
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
function cell(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return formatNumber(value)
  if (typeof value === "string" && value !== "") return value
  return "—"
}
