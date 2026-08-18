"use client"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import type { Citation } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { Figure } from "./figure"

/**
 * Where a block's figures came from, as a chip at the end of the sentence.
 *
 * The card list this replaces put a bordered panel of numbers between every
 * paragraph and the next, so an answer read as an answer followed by a receipt.
 * A chip says the same thing in the width of a word: *this claim has sources,
 * and there are this many of them*.
 *
 * **The chip is a disclosure, not a decoration.** ADR-0015 gives provenance two
 * layers, and the first one — the value, its unit, its `as_of`, whether it is
 * stale — may not be more than one press away from the claim it supports. So the
 * chip opens into exactly what the card used to show, in place, under the
 * paragraph it belongs to. Collapsing it was a change to the reading order, not
 * to what the reader is entitled to see.
 *
 * **No tool name reaches this DOM.** A citation carries one and it is
 * deliberately not read: the Tool Call Trace is the audit surface
 * (`docs/specs/0002` §9). What a chip is labelled with is `provenance` — where
 * the number came from, which is the part a reader can act on.
 */
export function CitationChips({
  citations,
  className,
}: {
  citations: Citation[]
  className?: string
}) {
  if (citations.length === 0) return null
  const label = chipLabel(citations)

  return (
    <Collapsible className={cn("inline", className)}>
      <CollapsibleTrigger
        className="ml-1.5 inline-flex max-w-[14rem] items-baseline gap-1 truncate rounded-md bg-surface-raised px-1.5 py-0.5 align-baseline text-micro text-ink-4 transition-colors hover:bg-surface-menu hover:text-ink-2"
        aria-label={`Nguồn của đoạn này (${citations.length})`}
      >
        {label}
      </CollapsibleTrigger>

      <CollapsibleContent>
        <ul className="mt-2 grid gap-2 rounded-xl bg-surface-raised px-3 py-2.5">
          {citations.map((citation, index) => (
            <li key={`${citation.field_path}-${index}`} className="grid gap-0.5 text-meta">
              <p className="font-mono text-micro text-ink-5">{citation.field_path}</p>
              <Figure
                value={citation.value}
                unit={citation.unit}
                asOf={citation.as_of}
                stale={citation.stale}
                sourceName={
                  citation.source === "external_claim" ? citation.provenance : null
                }
                retrievedAt={citation.source === "external_claim" ? citation.as_of : null}
              />
              {citation.interpretation && <p className="text-ink-3">{citation.interpretation}</p>}
              <p className="text-ink-5">Nguồn: {sourceName(citation)}</p>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}

/**
 * The chip's text: the first source, and how many others there are.
 *
 * Named after a source rather than counted alone — *masangroup +2* tells the
 * reader whose page the sentence rests on, where *3 nguồn* tells them only that
 * somebody's did. Distinct sources are counted, not citations: five figures from
 * one filing are one source, and calling them five would overstate how much
 * agreement is behind the claim.
 */
export function chipLabel(citations: Citation[]): string {
  const names: string[] = []
  for (const citation of citations) {
    const name = shortSource(citation)
    if (name && !names.includes(name)) names.push(name)
  }
  if (names.length === 0) return `${citations.length} nguồn`
  return names.length === 1 ? names[0] : `${names[0]} +${names.length - 1}`
}

/**
 * What one claim is called, short enough to sit inside a word's worth of space.
 *
 * **`provenance` is only read for a claim that came from outside.** On a
 * registered field the backend writes it as `"{tool}:{field}"` (`grounding.py`),
 * so printing it here would put a tool name on screen — the one thing this
 * surface may never do (`docs/specs/0002` §9). A store-derived claim gets the
 * vocabulary a reader can act on instead: *which kind of evidence this is*.
 */
function shortSource(citation: Citation): string {
  if (citation.source !== "external_claim" && citation.source !== "source_claim") {
    return sourceLabel(citation)
  }
  const raw = (citation.provenance || "").trim()
  if (!raw) return sourceLabel(citation)
  const host = raw.replace(/^https?:\/\//, "").split("/")[0]
  if (!host.includes(".")) return host
  const parts = host.replace(/^www\./, "").split(".")
  // The registrable label, which is the half a reader recognises: `masangroup`
  // out of `www.masangroup.com`, and `vnexpress` out of `e.vnexpress.net`.
  return parts.length > 2 ? parts[parts.length - 2] : parts[0]
}

/** The full source line under a figure, held to the same rule as the chip. */
function sourceName(citation: Citation): string {
  if (citation.source === "external_claim" || citation.source === "source_claim") {
    return citation.provenance || sourceLabel(citation)
  }
  return sourceLabel(citation)
}

/** What a claim that did not come from outside is called, in the reader's words. */
function sourceLabel(citation: Citation): string {
  switch (citation.source) {
    case "registered_field":
      return "chỉ số đã đăng ký"
    case "stored":
      return "dữ liệu đã lưu"
    case "source_claim":
      return "nguồn tin đã duyệt"
    case "external_claim":
      return "nguồn ngoài"
    case "derived":
      return "dữ liệu dẫn xuất"
    case "user_input":
      return "dữ liệu bạn cung cấp"
    default:
      return citation.source
  }
}
