"use client"

import { ChevronDown } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import type { Citation, ContentBlock } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { Figure } from "./figure"

/**
 * One proven presentation unit, and the figures it stands on.
 *
 * Facts, interpretation and reference actions read as visibly separate things
 * (`docs/specs/0002` §6), which is why a `recommendation` block is framed and
 * labelled rather than being another paragraph: it is the one kind of block the
 * Recommendation Gate can withhold, and a reader should be able to see which
 * part of an answer that was.
 *
 * Units and `as_of` sit **beside** the figures rather than behind the
 * disclosure, because a number without its unit and its date is the thing this
 * whole system exists to stop being said. Method detail — the registered field
 * id and the sanctioned interpretation — is what goes behind **View details**.
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
        "space-y-2",
        isRecommendation &&
          "rounded-md border border-sky-500/40 bg-sky-500/5 px-3 py-2",
        className,
      )}
    >
      {isRecommendation && (
        <p className="text-[11px] font-medium uppercase tracking-wide text-sky-600 dark:text-sky-400">
          Hành động tham chiếu
        </p>
      )}

      {/* `whitespace-pre-wrap` rather than a Markdown renderer: a block is
          already a Markdown-safe unit, and shipping a parser to interpret model
          output is a second place where what is stored and what is shown can
          disagree. */}
      <p className="whitespace-pre-wrap text-sm leading-relaxed">{block.text}</p>

      {block.citations.length > 0 && <Figures citations={block.citations} />}
    </div>
  )
}

function Figures({ citations }: { citations: Citation[] }) {
  return (
    <Collapsible className="rounded-md border border-border/60 bg-muted/20">
      <ul className="divide-y divide-border/50">
        {citations.map((citation, index) => (
          <li key={`${citation.field_path}-${index}`} className="px-2 py-1.5 text-xs">
            <Figure
              value={citation.value}
              unit={citation.unit}
              asOf={citation.as_of}
              stale={citation.stale}
            />
          </li>
        ))}
      </ul>

      <CollapsibleTrigger className="group flex w-full items-center gap-1 border-t border-border/60 px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground">
        View details
        <ChevronDown className="h-3 w-3 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none" />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <dl className="space-y-2 border-t border-border/60 px-2 py-2 text-xs">
          {citations.map((citation, index) => (
            <div key={`${citation.field_path}-detail-${index}`} className="space-y-0.5">
              <dt className="font-mono text-[11px] text-muted-foreground">
                {citation.field_path}
              </dt>
              {citation.interpretation && <dd>{citation.interpretation}</dd>}
              <dd className="text-muted-foreground">
                Source: {citation.source}
                {citation.provenance ? ` · ${citation.provenance}` : ""}
              </dd>
            </div>
          ))}
        </dl>
      </CollapsibleContent>
    </Collapsible>
  )
}
