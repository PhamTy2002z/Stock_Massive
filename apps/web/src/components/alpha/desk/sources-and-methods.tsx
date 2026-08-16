"use client"

import { ChevronDown } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import type { SourceAndMethod } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { Figure } from "./figure"

/**
 * Where the figures came from, on demand.
 *
 * Method detail appears here and nowhere in the answer itself
 * (`docs/specs/0002` §6): the conclusion is what the reader wanted, and a
 * provider name beside every number turns a paragraph into a footnote.
 *
 * **The tool name is not shown, and the row carries one.** `provider_source`
 * and the registered field are what a user can act on — where the number came
 * from and which computation it is. The tool that fetched it is an internal
 * name, and the Tool Call Trace is the surface for that (`docs/specs/0002` §9).
 */
export function SourcesAndMethods({
  rows,
  className,
}: {
  rows: SourceAndMethod[]
  className?: string
}) {
  if (rows.length === 0) return null

  return (
    <Collapsible className={cn("rounded-md border border-border/60", className)}>
      <CollapsibleTrigger className="group flex w-full items-center gap-1 px-3 py-2 text-xs text-muted-foreground hover:text-foreground">
        Sources &amp; methods
        <span className="tabular-nums">({rows.length})</span>
        <ChevronDown className="h-3 w-3 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none" />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <ul className="divide-y divide-border/50 border-t border-border/60">
          {rows.map((row, index) => (
            <li
              key={`${row.registered_field ?? "field"}-${index}`}
              className="space-y-0.5 px-3 py-2 text-xs"
            >
              <p className="font-mono text-[11px] text-muted-foreground">
                {row.registered_field ?? "—"}
              </p>
              <Figure
                value={row.value}
                unit={row.unit}
                asOf={row.freshness?.as_of ?? null}
                stale={row.freshness?.stale ?? false}
              />
              {row.interpretation && <p>{row.interpretation}</p>}
              <p className="text-muted-foreground">Source: {row.provider_source}</p>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}
