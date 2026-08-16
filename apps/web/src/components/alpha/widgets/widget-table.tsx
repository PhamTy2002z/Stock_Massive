"use client"

import { cn } from "@/lib/utils"
import { WIDGET_PALETTE } from "./palette"

/**
 * The data-table equivalent every Widget carries.
 *
 * One table rather than four, because the accessibility requirement is the same
 * requirement in all four cases and four copies is how one of them ends up
 * without a caption. The caption is not decoration: it is what a screen reader
 * announces before the rows, and it is where the data date goes.
 */
export interface WidgetTableProps {
  caption: string
  columns: string[]
  rows: (string | number)[][]
}

// Written out as literals rather than composed from `WIDGET_PALETTE`, because
// Tailwind's arbitrary-value syntax is scanned as source text and a class built
// from a variable is a class that never reaches the stylesheet. Both spellings
// name the *same* custom property, which is the invariant that matters: the
// value is still declared in exactly one place.
const HEAD_CELL = "border-b border-[hsl(var(--widget-grid))] py-1.5 font-medium"
const BODY_CELL = "border-b border-[hsl(var(--widget-grid))] py-1.5"

export function WidgetTable({ caption, columns, rows }: WidgetTableProps) {
  return (
    <table className="w-full border-collapse text-[13px] leading-[1.43]">
      <caption className="pb-2 text-left" style={{ color: WIDGET_PALETTE.inkMuted }}>
        {caption}
      </caption>
      <thead>
        <tr>
          {columns.map((column, index) => (
            <th
              key={column}
              scope="col"
              className={
                index === 0
                  ? cn(HEAD_CELL, "text-left")
                  : cn(HEAD_CELL, "text-right")
              }
            >
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row[0])}>
            {row.map((cell, index) => (
              <td
                key={columns[index] ?? index}
                className={
                  index === 0
                    ? cn(BODY_CELL, "text-left")
                    : cn(BODY_CELL, "text-right tabular-nums")
                }
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
