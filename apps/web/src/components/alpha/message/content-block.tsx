"use client"

import { useState } from "react"

import type { ContentBlock } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { CitationChips } from "./citation-chips"
import { Markdown } from "./markdown"
import { SourceIcon } from "./source-list"

/**
 * One proven presentation unit, and the figures it stands on.
 *
 * Facts, interpretation and reference actions read as visibly separate things
 * (`docs/specs/0002` §6), which is why a `recommendation` block is framed and
 * labelled rather than being another paragraph: it is the one kind of block the
 * Recommendation Gate can withhold, and a reader should be able to see which
 * part of an answer that was.
 *
 * Units and `as_of` sit one press behind the chip at the end of the claim
 * (`citation-chips`), never further: a number without its unit and its date is
 * the thing this whole system exists to stop being said, and ADR-0015's first
 * provenance layer has to stay reachable from the sentence it supports.
 *
 * `block.source_ids` is the *other* provenance question and gets its own row.
 * A citation chip answers "which figure, in what unit, on what date"; a source
 * chip answers "whose page is behind this passage" — and a reader checking a
 * claim about a chairman's appointment wants the page, not the figure panel.
 * Collapsing the two into one chip would mean one of the two questions stops
 * being answerable.
 *
 * **No tool name reaches this component's DOM.** A citation carries one, and it
 * is deliberately not read: the trace is an audit surface, not part of the
 * answer (`docs/specs/0002` §9).
 *
 * `block.unverified_figures` is carried and deliberately not rendered, the same
 * way `AssistantView.riskNotice` is. The grounding pass still records which
 * figures it could not tie to evidence — that is what withholds a
 * recommendation block — but the reader was shown that record as a list of bare
 * literals ("4, 1.000, 2026"), which reads as a defect in the answer rather
 * than as provenance. The downgrade stays server-side, where it decides
 * something.
 *
 * `stagger` is **latched at mount**. It says "this block is the one that just
 * arrived", and that stops being true the moment the next event lands — an
 * activity event a beat later would otherwise cut the cascade off mid-sentence.
 * A block never changes once appended, so what was true at mount stays the right
 * answer; history and a reconnect's snapshot mount with it false and render at
 * once.
 */
export function ContentBlockView({
  block,
  stagger = false,
  className,
}: {
  block: ContentBlock
  /** This block was just delivered: cascade its prose in a few words at a time. */
  stagger?: boolean
  className?: string
}) {
  const [cascade] = useState(stagger)
  const isRecommendation = block.kind === "recommendation"

  return (
    <div
      className={cn(
        "space-y-2.5",
        // The one callout the reference frames in amber — the same treatment its
        // "ask VisgniteAI about this board" strip gets. A tinted surface, not a
        // filled control, so it does not spend the amber budget.
        isRecommendation &&
          "rounded-card border border-primary/25 bg-primary/[0.05] px-3.5 py-3",
        className,
      )}
    >
      {isRecommendation && (
        <p className="text-eyebrow font-semibold uppercase text-primary">
          Hành động tham chiếu
        </p>
      )}

      {/* A block *is* a Markdown-safe unit — that is what ADR-0013 buffers the
          provider's deltas into — so it is rendered as Markdown rather than
          shown verbatim. Rendering it verbatim was the bug: `**Nguyễn Đăng
          Quang**` reached readers with its asterisks. The renderer has no raw
          HTML path, so nothing in a block can produce markup. */}
      <Markdown
        text={block.text}
        stagger={cascade}
        trailing={
          block.citations.length > 0 ? (
            <CitationChips citations={block.citations} />
          ) : undefined
        }
      />

      <BlockSources urls={block.source_ids ?? []} />
    </div>
  )
}

/**
 * The pages behind one passage, as chips under it.
 *
 * A row of its own rather than a `trailing` chip inside the last sentence: this
 * is not a mark on a single claim the way a citation is, it is what the passage
 * as a whole was read out of, and several of them do not fit inside a line of
 * prose without breaking it apart.
 *
 * Renders nothing when there is nothing to render, and — this is the property
 * that matters — cannot do worse than that. A bad URL costs its own chip and no
 * more, because `source_ids` is display metadata (`lib/alpha-desk/types`): the
 * block above it is the answer, and a throw here would take that answer out of
 * the transcript over a label.
 */
function BlockSources({ urls }: { urls: unknown[] }) {
  const sources = webSources(urls)
  if (sources.length === 0) return null

  return (
    <ul className="flex flex-wrap items-center gap-1.5">
      {sources.map((source) => (
        <li key={source.url}>
          <a
            href={source.url}
            target="_blank"
            // `noreferrer` alongside `noopener` for the reason `source-list`
            // gives: these are untrusted external pages opened from an
            // authenticated surface, and the referrer would tell each of them
            // which app sent the reader.
            rel="noopener noreferrer"
            className="inline-flex max-w-[12rem] items-center gap-1 rounded-md bg-surface-raised px-1.5 py-0.5 text-micro text-ink-4 transition-colors hover:bg-surface-menu hover:text-ink-2"
          >
            <SourceIcon domain={source.domain} />
            <span className="truncate">{source.domain}</span>
          </a>
        </li>
      ))}
    </ul>
  )
}

/**
 * The linkable sources out of a raw id list, and nothing else.
 *
 * Typed `unknown[]` on purpose: the list arrives off the wire, and the interface
 * saying `string[]` is a description of the contract rather than a guarantee
 * about the bytes. Three things are dropped rather than rendered:
 *
 * - anything `URL` cannot parse, including a relative path, which is not an
 *   external page and so is not a source;
 * - any scheme but http(s). `new URL("javascript:alert(1)")` parses happily, and
 *   putting that in an `href` would make a mislabelled block a clickable script;
 * - a repeat of a URL already shown, since a page cited twice is one page.
 *
 * Two different pages on one host each keep a chip, both reading as the same
 * domain: they are different pages, and hiding one would misstate how much the
 * passage rests on.
 */
function webSources(urls: unknown[]): { url: string; domain: string }[] {
  const chips: { url: string; domain: string }[] = []
  const seen = new Set<string>()

  for (const raw of urls) {
    if (typeof raw !== "string" || seen.has(raw)) continue
    let parsed: URL
    try {
      parsed = new URL(raw)
    } catch {
      continue
    }
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") continue
    if (!parsed.hostname) continue
    seen.add(raw)
    // `www.` stripped and the host lowercased, which is what the backend's own
    // `domain_of` does — so the label under a chip reads the same as the label
    // in the progress trail for the same page.
    chips.push({
      url: raw,
      domain: parsed.hostname.toLowerCase().replace(/^www\./, ""),
    })
  }

  return chips
}

