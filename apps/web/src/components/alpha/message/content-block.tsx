"use client"

import type { ContentBlock } from "@/lib/alpha-desk/types"
import { UNVERIFIED_FIGURES_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"
import { CitationChips } from "./citation-chips"
import { Markdown } from "./markdown"

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
 * **No tool name reaches this component's DOM.** A citation carries one, and it
 * is deliberately not read: the trace is an audit surface, not part of the
 * answer (`docs/specs/0002` §9).
 */
export function ContentBlockView({
  block,
  className,
}: {
  block: ContentBlock
  className?: string
}) {
  const isRecommendation = block.kind === "recommendation"

  return (
    <div
      className={cn(
        "space-y-2.5",
        // The one callout the reference frames in teal — the same treatment its
        // "ask VisgniteAI about this board" strip gets. A tinted surface, not a
        // filled control, so it does not spend the teal budget.
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
        trailing={
          block.citations.length > 0 ? (
            <CitationChips citations={block.citations} />
          ) : undefined
        }
      />

      {(block.unverified_figures?.length ?? 0) > 0 && (
        <p
          role="note"
          className="rounded-lg border border-caution/35 bg-caution/5 px-2.5 py-2 text-meta text-caution"
        >
          <span className="font-semibold">{UNVERIFIED_FIGURES_COPY.label}.</span>{" "}
          {UNVERIFIED_FIGURES_COPY.detail(block.unverified_figures ?? [])}
        </p>
      )}

    </div>
  )
}

