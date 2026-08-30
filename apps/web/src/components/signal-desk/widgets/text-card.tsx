"use client"

/**
 * A few lines of text lifted straight out of a frame, and nothing written here.
 *
 * There is exactly one honest use for prose on a board: text the *engine* put in
 * a frame — a filing's line item name, a refusal's own sentence, a period label.
 * So this reads cells and prints them, and it has no way to compose a sentence
 * of its own. A card that could would be the surface making a claim, which is
 * what the caption's reference scheme exists to prevent.
 */

import { columnIndex, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"

export function TextCardWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const textColumn =
    typeof options.text === "string" ? options.text : frame.columns[1]
  const label = columnIndex(frame, labelColumn)
  const body = columnIndex(frame, textColumn)

  if (frame.rows.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có ghi chú nào.</p>
  }

  return (
    <dl className="m-0 space-y-2 rounded-lg border border-hairline bg-surface-sunken px-3 py-2.5">
      {frame.rows.map((row, index) => (
        <div key={index} className="min-w-0">
          <dt className="text-meta text-muted-foreground">{textAt(row, label)}</dt>
          <dd className="text-pretty text-sm leading-relaxed text-ink-2">
            {textAt(row, body)}
          </dd>
        </div>
      ))}
    </dl>
  )
}
