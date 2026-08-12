"use client"

/** PROTOTYPE — issue #22, Variant A: thread-first three-rail desk. */

import { MessageSquare, Plus } from "lucide-react"
import type { HarnessState } from "./fixtures"
import { Conversation, MobileRailMenu, RailHeading, symbolForState, ThreadList, Watchlist } from "./shared"

export const VARIANT_A_NAME = "Thread-first desk"

export function VariantA({ state }: { state: HarnessState }) {
  const activeSymbol = symbolForState(state)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-11 shrink-0 items-center gap-2 border-b border-border bg-card px-3 lg:hidden">
        <MobileRailMenu label="Threads" kind="threads" />
        <MobileRailMenu label="Watchlist" kind="watchlist" />
        <span className="ml-auto text-[10px] text-muted-foreground">A · three rails</span>
      </div>
      <div className="grid min-h-0 flex-1 lg:grid-cols-[14.5rem_minmax(0,1fr)_12.5rem]">
        <aside className="hidden min-h-0 overflow-y-auto border-r border-border bg-card lg:block">
          <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
            <span className="text-[13px] font-semibold">Threads</span>
            <button type="button" className="rounded-md bg-foreground p-1.5 text-background">
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          <RailHeading action="search">Recent</RailHeading>
          <div className="px-1.5"><ThreadList /></div>
        </aside>

        <main className="min-h-0 min-w-0">
          <Conversation state={state} />
        </main>

        <aside className="hidden min-h-0 overflow-y-auto border-l border-border bg-card lg:block">
          <div className="border-b border-border px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold">Watchlist</span>
              <span className="text-[10px] text-muted-foreground">5/10</span>
            </div>
            <p className="mt-0.5 text-[9.5px] text-muted-foreground">2 Analysis mới</p>
          </div>
          <RailHeading action="plus">Symbols</RailHeading>
          <div className="px-1.5"><Watchlist activeSymbol={activeSymbol} /></div>
          <div className="mx-2.5 mt-4 rounded-lg border border-dashed border-border p-2 text-[9.5px] leading-relaxed text-muted-foreground">
            <MessageSquare className="mb-1 h-3.5 w-3.5" />
            Thread có thể chạm nhiều mã. Watchlist chỉ quyết định mã nào được chạy lại mỗi phiên.
          </div>
        </aside>
      </div>
    </div>
  )
}
