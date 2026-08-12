"use client"

/** PROTOTYPE — issue #22, Variant B: symbol-first workspace. */

import { ChevronDown, Plus, Search } from "lucide-react"
import type { HarnessState } from "./fixtures"
import { Conversation, RailHeading, symbolForState, Watchlist } from "./shared"

export const VARIANT_B_NAME = "Symbol-first workspace"

export function VariantB({ state }: { state: HarnessState }) {
  const activeSymbol = symbolForState(state)
  return (
    <div className="grid h-full min-h-0 bg-background lg:grid-cols-[15.5rem_minmax(0,1fr)]">
      <aside className="hidden min-h-0 overflow-y-auto border-r border-border bg-card lg:block">
        <div className="border-b border-border px-3 py-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] font-semibold">My Watchlist</p>
              <p className="mt-0.5 text-[9.5px] text-muted-foreground">5/10 · 2 unread</p>
            </div>
            <button type="button" className="rounded-lg bg-foreground p-1.5 text-background">
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mt-2 flex items-center gap-1.5 rounded-lg border border-input px-2 py-1.5 text-[10px] text-muted-foreground">
            <Search className="h-3 w-3" /> Add a Universe symbol
          </div>
        </div>
        <RailHeading>Analysis status</RailHeading>
        <div className="px-1.5"><Watchlist activeSymbol={activeSymbol} /></div>
      </aside>

      <section className="flex min-h-0 min-w-0 flex-col">
        <div className="shrink-0 border-b border-border bg-card px-3 py-2">
          <div className="lg:hidden"><Watchlist horizontal activeSymbol={activeSymbol} /></div>
          <div className="hidden items-center gap-2 lg:flex">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{activeSymbol} threads</span>
            <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto">
              <button type="button" className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-medium">Sau phiên 11/08</button>
              <button type="button" className="rounded-full px-2.5 py-1 text-[10px] text-muted-foreground hover:bg-secondary">Chất lượng tài sản</button>
              <button type="button" className="rounded-full px-2.5 py-1 text-[10px] text-muted-foreground hover:bg-secondary">So với BID</button>
            </div>
            <button type="button" className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px]">
              All threads <ChevronDown className="h-3 w-3" />
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1">
          <Conversation state={state} roomy />
        </div>
      </section>
    </div>
  )
}
