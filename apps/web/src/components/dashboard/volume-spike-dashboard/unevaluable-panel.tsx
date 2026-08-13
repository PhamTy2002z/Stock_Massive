"use client"

import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { signalIssueSentences } from "@/lib/signal-issues"
import type { UnevaluableSymbol } from "@/lib/api"

/**
 * The symbols the store could not answer for, one click away.
 *
 * Behind a disclosure rather than hidden: the count is on screen at all times,
 * because it is the difference between "five spikes out of fifty companies" and
 * "five out of twelve", and the reader has no way to ask for it later.
 */
export function UnevaluablePanel({
  symbols,
  className,
}: {
  symbols: UnevaluableSymbol[]
  className?: string
}) {
  const [open, setOpen] = useState(false)

  if (symbols.length === 0) return null

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={cn("space-y-2", className)}>
      <CollapsibleTrigger className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", open && "rotate-180")}
        />
        {symbols.length} mã chưa tính được tín hiệu
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="rounded-lg border border-border/50 bg-card/50 divide-y divide-border/30">
          {symbols.map((item) => (
            <li
              key={item.symbol}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
            >
              <span className="font-medium">{item.symbol}</span>
              <span className="text-muted-foreground">
                {signalIssueSentences(item.issues).join(" • ")}
              </span>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}
