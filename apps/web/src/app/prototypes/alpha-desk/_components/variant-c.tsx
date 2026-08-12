"use client"

/** PROTOTYPE — issue #22, Variant C: conversation-first, rails become docks. */

import { ChevronDown, History, Plus, Sparkles } from "lucide-react"
import type { HarnessState } from "./fixtures"
import { Conversation, symbolForState, ThreadList, Watchlist } from "./shared"

export const VARIANT_C_NAME = "Conversation-first canvas"

export function VariantC({ state }: { state: HarnessState }) {
  const activeSymbol = symbolForState(state)
  return (
    <div className="relative flex h-full min-h-0 flex-col bg-background">
      <div className="z-20 flex shrink-0 items-center gap-2 border-b border-border bg-card px-3 py-2">
        <details className="relative">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-[10px] font-medium">
            <History className="h-3.5 w-3.5" /> Threads <ChevronDown className="h-3 w-3" />
          </summary>
          <div className="absolute left-0 top-full z-30 mt-1 w-72 rounded-xl border border-border bg-popover p-2 shadow-xl">
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="text-[11px] font-semibold">Recent Threads</span>
              <Plus className="h-3.5 w-3.5" />
            </div>
            <ThreadList />
          </div>
        </details>
        <div className="min-w-0 flex-1"><Watchlist horizontal activeSymbol={activeSymbol} /></div>
        <button type="button" className="hidden shrink-0 items-center gap-1 rounded-lg bg-foreground px-2.5 py-1.5 text-[10px] text-background sm:flex">
          <Sparkles className="h-3 w-3" /> New Thread
        </button>
      </div>

      <div className="min-h-0 flex-1">
        <Conversation state={state} roomy />
      </div>

      <div className="pointer-events-none absolute bottom-20 left-3 z-10 hidden xl:block">
        <div className="pointer-events-auto w-40 rounded-xl border border-border bg-card/95 p-2 shadow-lg backdrop-blur">
          <p className="px-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">In this Thread</p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            <code className="rounded bg-secondary px-1.5 py-1 text-[9px]">{activeSymbol}</code>
            <button type="button" className="rounded border border-dashed border-border px-1.5 py-1 text-[9px] text-muted-foreground">+ symbol</button>
          </div>
          <p className="mt-2 px-1 text-[9px] leading-snug text-muted-foreground">Free-roaming Thread; symbols are context, not ownership.</p>
        </div>
      </div>
    </div>
  )
}
