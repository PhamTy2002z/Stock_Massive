"use client"

/**
 * One sentence under a picture, with every figure marked and traceable.
 *
 * The template arrives with its holes intact — `{a}`, `{b}` — and the cells that
 * fill them arrive resolved beside it. So the sentence is assembled here rather
 * than taken pre-joined, which is what lets each figure be a `<mark>` a reader
 * can hover to see the cell it came from. The joined text also travels, and it
 * is what an export and a screen reader get.
 *
 * **No number is formatted here and none is computed.** `ref.text` is what the
 * server wrote. A caption that did arithmetic on the values it was handed would
 * be the browser making a market claim, which is precisely what the reference
 * scheme exists to prevent.
 *
 * A placeholder with no cell behind it is refused server-side, so one reaching
 * here means the two builds disagree; it is drawn as itself rather than as an
 * empty space, because a sentence with a hole is a hole the reader can see.
 */

import type { CaptionBlock } from "@/lib/alpha-desk/types"

const PLACEHOLDER = /(\{[a-z]\})/g

export function CaptionWidget({ caption }: { caption: CaptionBlock }) {
  const parts = caption.template.split(PLACEHOLDER)

  return (
    <p className="rounded-lg border border-hairline bg-surface-sunken px-3 py-2.5 text-pretty text-sm leading-relaxed text-ink-2">
      {parts.map((part, index) => {
        const key = part.length === 3 ? part.slice(1, 2) : null
        const ref = key === null ? undefined : caption.refs[key]
        if (ref === undefined) return <span key={index}>{part}</span>
        return (
          <mark
            key={index}
            // A mark rather than a colour: the figure is emphasis, not a claim
            // about direction, and the colours in this palette all mean
            // something the engine said.
            className="rounded bg-transparent px-0.5 font-mono font-semibold tabular-nums text-foreground"
            title={`${ref.column} · dòng ${ref.row + 1}`}
          >
            {ref.text}
          </mark>
        )
      })}
    </p>
  )
}
