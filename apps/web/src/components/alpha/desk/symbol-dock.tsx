"use client"

import { ChevronDown, FileText } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { STATE_DOT, STATE_LABEL, sessionLabel } from "@/components/alpha/watchlist-rail"
import type { AnalysisState } from "@/lib/alpha"
import { cn } from "@/lib/utils"

export interface DockSymbol {
  symbol: string
  state: AnalysisState
  verdict: string | null
  unread: boolean
  /**
   * The session of the newest Analysis this symbol has, or null for one that
   * has never been analysed. A `failed` symbol still has an older Analysis and
   * still opens it — an empty cell tells the user there is nothing to see when
   * a month of history exists (`docs/specs/0002` §3).
   */
  latestTradingDay: string | null
}

/**
 * The Watchlist as a compact persistent dock.
 *
 * A strip, not a column. Chat owns the main canvas and almost all available
 * width (`docs/specs/0002` §2), so the durable set of symbols is a row of chips
 * across the top with the session and the cap beside it, and the rail itself —
 * adding, removing, retrying, reading an Analysis — lives behind a disclosure.
 * A permanent full-height rail would be a second navigation level competing
 * with the conversation for the only thing the conversation needs.
 *
 * **The chips scroll horizontally; the page never does.** On a narrow viewport
 * the dock is what moves, and the layout is not replaced by a different one
 * (`docs/specs/0002` §8).
 *
 * Selecting a chip changes the active lens and nothing else. It starts no
 * Thread, because a Thread is free-roaming and is never owned by a symbol.
 *
 * The chips are a projection of the rail rather than a second implementation of
 * it: the state vocabulary — label and colour — is the rail's own
 * (`state-copy.ts`), and adding, removing, retrying and reading an Analysis all
 * happen in `WatchlistRail`, mounted here as the disclosure's content. What the
 * strip adds is the one thing the rail has no notion of, because it predates
 * the conversation: which symbol the answer is being read against.
 */
export function SymbolDock({
  symbols,
  activeSymbol,
  onSelect,
  onOpenAnalysis,
  tradingDay,
  count,
  cap,
  children,
  className,
}: {
  symbols: DockSymbol[]
  activeSymbol: string | null
  onSelect: (symbol: string | null) => void
  /** Opening one renders it inline in the transcript and advances its badge. */
  onOpenAnalysis: (symbol: string, tradingDay: string) => void
  tradingDay: string | null
  count: number
  cap: number
  /** The Watchlist rail itself, mounted by the container behind the disclosure. */
  children: React.ReactNode
  className?: string
}) {
  // Counted from the chips rather than passed in beside them: two sources for
  // one number is one source too many, and the caller already handed over the
  // list the count is of.
  const unreadCount = symbols.filter((entry) => entry.unread).length
  // A symbol arriving by deep link need not be on the Watchlist, and adding it
  // silently is exactly what must not happen. It gets a chip so the lens is
  // visible, marked so its absence from the rail is not read as a bug.
  const lensOnly =
    activeSymbol !== null && !symbols.some((entry) => entry.symbol === activeSymbol)

  return (
    <Collapsible className={cn("shrink-0 border-b border-border bg-background", className)}>
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="flex shrink-0 items-center gap-2 text-xs">
          <span className="font-medium">Watchlist</span>
          {unreadCount > 0 && (
            <span
              aria-label={`${unreadCount} unread Analyses`}
              className="rounded-full bg-primary px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-white"
            >
              {unreadCount}
            </span>
          )}
          <span
            aria-label={`${count} of ${cap} symbols`}
            className="rounded-md border border-border px-1.5 py-0.5 tabular-nums text-muted-foreground"
          >
            {count}/{cap}
          </span>
          <span className="hidden text-muted-foreground sm:inline">
            {sessionLabel(tradingDay)}
          </span>
        </div>

        {/* `min-w-0` is what keeps this from widening the flex row past the
            viewport: without it the chip list sizes to its content and the page
            body gains a horizontal scrollbar instead of the dock. */}
        <div className="scrollbar-thin min-w-0 flex-1 overflow-x-auto">
          <ul className="flex items-center gap-1" aria-label="Symbols">
            {lensOnly && (
              <SymbolChip
                symbol={activeSymbol}
                isActive
                subtitle="ngoài Watchlist"
                onSelect={() => onSelect(null)}
              />
            )}
            {symbols.map((entry) => (
              <SymbolChip
                key={entry.symbol}
                symbol={entry.symbol}
                isActive={entry.symbol === activeSymbol}
                subtitle={entry.verdict}
                unread={entry.unread}
                state={entry.state}
                onSelect={() =>
                  onSelect(entry.symbol === activeSymbol ? null : entry.symbol)
                }
                onOpenAnalysis={
                  entry.latestTradingDay === null
                    ? undefined
                    : () => onOpenAnalysis(entry.symbol, entry.latestTradingDay!)
                }
              />
            ))}
          </ul>
        </div>

        <CollapsibleTrigger className="group inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">
          Manage
          <ChevronDown className="h-3 w-3 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none" />
        </CollapsibleTrigger>
      </div>

      {/* Bounded and scrolling. The rail claims no height of its own, and the
          dock is the thing that decides how much of the screen it may take. */}
      <CollapsibleContent>
        <div className="max-h-[50vh] overflow-y-auto border-t border-border px-3 py-3">
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

/**
 * One chip, and the two different things a user can do with a symbol.
 *
 * Selecting changes the lens; opening the Analysis puts the artifact in the
 * transcript. They are separate controls rather than one because they mean
 * different things — the lens organises what the next answer is read against,
 * and opening an Analysis is the act that advances that symbol's badge. A
 * single control doing both would clear a badge every time someone changed the
 * subject.
 */
function SymbolChip({
  symbol,
  isActive,
  subtitle,
  unread,
  state,
  onSelect,
  onOpenAnalysis,
}: {
  symbol: string
  isActive: boolean
  subtitle: string | null
  unread?: boolean
  state?: AnalysisState
  onSelect: () => void
  /** Absent for a symbol with no Analysis at all: there is nothing to open. */
  onOpenAnalysis?: () => void
}) {
  return (
    <li
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-md border text-xs",
        isActive
          ? "border-foreground/40 bg-muted font-medium"
          : "border-border text-muted-foreground",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={isActive}
        className="inline-flex items-center gap-1.5 rounded-l-md px-2 py-1 hover:bg-muted"
      >
        {/* The rail's own colour and the rail's own word for it, so a symbol
            never reads amber here and red three lines below. */}
        {state && (
          <span
            aria-label={STATE_LABEL[state]}
            title={STATE_LABEL[state]}
            className={cn("h-1.5 w-1.5 rounded-full", STATE_DOT[state])}
          />
        )}
        <span>{symbol}</span>
        {subtitle && <span className="text-muted-foreground">· {subtitle}</span>}
        {unread && (
          <span
            aria-label={`${symbol} has an unread Analysis`}
            className="h-1.5 w-1.5 rounded-full bg-primary"
          />
        )}
      </button>

      {onOpenAnalysis && (
        <button
          type="button"
          onClick={onOpenAnalysis}
          aria-label={`Open ${symbol} Analysis`}
          title={`Open ${symbol} Analysis`}
          className="rounded-r-md border-l border-border px-1.5 py-1 hover:bg-muted"
        >
          <FileText className="h-3 w-3" />
        </button>
      )}
    </li>
  )
}
