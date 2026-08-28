"use client"

/**
 * Six statements, each with a status the server computed, and no score.
 *
 * No chart library, and not a table either. A checklist is a list, and the shape
 * a reader scans is *label on the left, mark on the right* — a table would put
 * the same six sentences behind a header row and column sorting, which invites
 * the one reading this block is designed not to support: sort by status, count
 * the ticks, treat the count as a verdict.
 *
 * **The wording arrives; it is never composed here.** The labels are constants
 * in the Study that measured them (`studies/entry_condition_review.py`), and the
 * only Vietnamese this component owns is the three status words. A widget that
 * rephrased a condition would be a second author of a claim about a company.
 *
 * **Three statuses, and the third is not a failure.** `unknown` means the input
 * was not there — an unfiled quarter, a window too short — and drawing it as a
 * cross would say the condition was tested and did not hold. It gets its own
 * mark, its own colour and its own word.
 *
 * **The status is not colour alone.** Every row carries the status as text for a
 * screen reader, and the mark differs in shape as well as in hue, because a
 * reader who cannot separate green from red still has to be able to read this.
 */

import { Check, Minus, X } from "lucide-react"

import type { Frame } from "@/lib/alpha-desk/types"

import { columnIndex, formatMeasure, numberAt } from "../frame"
import type { WidgetProps } from "../widget-registry"

/** The three statuses a Study may send, and how each one reads. */
const STATUSES = {
  met: { word: "Đạt", icon: Check, tone: "text-positive" },
  not_met: { word: "Chưa đạt", icon: X, tone: "text-negative" },
  unknown: { word: "Chưa rõ", icon: Minus, tone: "text-caution" },
} as const

type Known = keyof typeof STATUSES

export function ConditionChecklistWidget({ frame, options }: WidgetProps) {
  const label = column(frame, options.label, "label", 0)
  const status = column(frame, options.status, "status", 1)
  const value = column(frame, options.value, "value")
  const unit = column(frame, options.unit, "unit")
  const evidence = column(frame, options.evidence, "evidence")
  const note = typeof options.note === "string" ? options.note : null

  if (frame.rows.length === 0) {
    return (
      <p className="text-meta text-muted-foreground">
        Không có điều kiện nào để hiển thị.
      </p>
    )
  }

  return (
    <figure className="m-0">
      <ul className="space-y-0">
        {frame.rows.map((row, index) => {
          const token = text(row, status)
          const reading = STATUSES[token as Known] ?? STATUSES.unknown
          const Mark = reading.icon
          return (
            <li
              key={index}
              className="flex items-start gap-2 border-b border-hairline py-1.5 last:border-0"
              // Which frame holds the number behind this row. Kept out of the
              // reading and available on hover: it is what makes a row
              // checkable, and it is not what a reader is here to read.
              title={
                evidence >= 0 ? `Số liệu trong khối ${text(row, evidence)}` : undefined
              }
            >
              <Mark className={`mt-0.5 size-3.5 shrink-0 ${reading.tone}`} aria-hidden />
              <span className="flex-1 text-pretty text-meta text-ink-2">
                {text(row, label)}
              </span>
              <span className="shrink-0 whitespace-nowrap font-mono text-meta tabular-nums text-muted-foreground">
                {measurement(row, value, unit)}
              </span>
              <span className="sr-only">{reading.word}</span>
            </li>
          )
        })}
      </ul>

      {note !== null && (
        <figcaption className="mt-2 text-pretty text-meta text-muted-foreground">
          {note}
        </figcaption>
      )}
    </figure>
  )
}

/** Where one column sits: by the server's option, by name, or by position. */
function column(
  frame: Frame,
  option: unknown,
  name: string,
  position?: number,
): number {
  const named = columnIndex(frame, typeof option === "string" ? option : name)
  if (named >= 0) return named
  return position ?? -1
}

/** One cell as the text it holds, and nothing invented for an absent one. */
function text(row: unknown[], index: number): string {
  if (index < 0 || index >= row.length) return ""
  const cell = row[index]
  return typeof cell === "string" ? cell : ""
}

/**
 * The number behind a row, with its unit, or an em dash for an absent one.
 *
 * An em dash rather than a zero, for the reason it is one everywhere else on
 * this panel: a condition with no measurement is a condition nothing measured,
 * and `0` would be a reading.
 */
function measurement(row: unknown[], value: number, unit: number): string {
  const measured = numberAt(row, value)
  return measured === null ? "—" : formatMeasure(measured, text(row, unit))
}
