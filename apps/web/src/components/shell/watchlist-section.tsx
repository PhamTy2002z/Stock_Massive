"use client"

import { useMemo, useState, type KeyboardEvent } from "react"
import { useQuery } from "@tanstack/react-query"
import { Plus, X } from "lucide-react"

import { searchStocks } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"
import { indexBySymbol, usePriceBoard } from "@/hooks/use-price-board"
import { useRailMutations, useWatchlistRail } from "@/hooks/use-watchlist-rail"
import { cn } from "@/lib/utils"

import { useShell } from "./shell-state"
import { STATE_DOT, stateSentence } from "./analysis-state"
import { deltaClass, Figure, IconButton, price, QuietLine, signedPercent } from "./primitives"

/**
 * The Watchlist, as the sidebar draws it.
 *
 * Two resources, joined here rather than on the server: the rail knows *which*
 * symbols this account follows and what state their Analysis is in, and the
 * price board knows what those symbols did today. Neither endpoint answers the
 * other's question, and asking the API for a joined shape would put a screen's
 * layout into a backend route.
 *
 * Selecting a row sets the conversation's analysis context and nothing else.
 * It opens no Thread, closes none, and writes nothing to the Watchlist — the
 * only writes here are the explicit add and the explicit remove.
 *
 * Each row leads with its Analysis state as a coloured dot whose accessible
 * name is the whole sentence (`./analysis-state`). A dot rather than the
 * sentence itself because the row is one line and ten sentences would be a
 * paragraph; the sentence rather than the state's name because two of the
 * five states differ only in why they are waiting.
 */
export function WatchlistSection() {
  const { state, dispatch } = useShell()
  const rail = useWatchlistRail()
  const { add, remove } = useRailMutations()
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState("")

  const symbols = useMemo(
    () => (rail.data?.entries ?? []).map((entry) => entry.symbol),
    [rail.data],
  )
  const board = usePriceBoard(symbols)
  const quotes = useMemo(() => indexBySymbol(board.data), [board.data])

  // Debounce-free on purpose: the query key *is* the text, so TanStack keeps
  // one request per distinct term and cancels nothing the user still wants.
  const term = draft.trim()
  const hits = useQuery({
    queryKey: queryKeys.stockSearch(term, 5),
    queryFn: () => searchStocks(term, 5),
    enabled: adding && term.length > 0,
    staleTime: STALE_TIME.STATIC,
  })

  const entries = rail.data?.entries ?? []
  const cap = rail.data?.cap ?? 0
  const count = rail.data?.count ?? 0
  const full = cap > 0 && count >= cap
  // The session every row's state is about. One value for the whole list: the
  // rail is answered for one Trading Day, and a per-row reading of it would
  // let two rows disagree about which session they are describing.
  const tradingDay = rail.data?.trading_day ?? null

  function submit(symbol: string) {
    const code = symbol.trim().toUpperCase()
    if (!code || full) return
    add.mutate(code)
    setDraft("")
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault()
      submit(hits.data?.[0]?.symbol ?? draft)
    }
    if (event.key === "Escape") {
      setAdding(false)
      setDraft("")
    }
  }

  return (
    <>
      <div className="flex flex-none items-center gap-2 px-4 pb-1.5 pt-[18px]">
        <span className="text-micro tracking-[0.02em] text-ink-6">Mã theo dõi</span>
        {cap > 0 && (
          <Figure className="rounded-[5px] bg-foreground/[0.06] px-1.5 py-[0.06em] text-micro text-ink-5">
            {count}/{cap}
          </Figure>
        )}
        <IconButton
          label={full ? "Danh sách đã đầy" : "Thêm mã"}
          size="sm"
          disabled={full}
          onClick={() => {
            setAdding((open) => !open)
            setDraft("")
          }}
          className="ml-auto size-[22px] rounded-md bg-foreground/[0.05] text-ink-4 hover:bg-primary/[0.16] hover:text-primary"
        >
          <Plus className="size-3.5" strokeWidth={2} />
        </IconButton>
      </div>

      {adding && (
        <div className="px-3 pb-1.5 pt-0.5">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            autoFocus
            aria-label="Tìm mã để thêm vào danh sách theo dõi"
            placeholder="Tìm mã · Enter để thêm"
            className="w-full rounded-lg border border-primary/[0.32] bg-surface-sunken px-2.5 py-1.5 font-mono text-control uppercase text-foreground outline-none placeholder:text-ink-6 placeholder:normal-case"
          />

          {(hits.data ?? []).length > 0 && (
            <div className="mt-1.5 animate-vg-row-in overflow-hidden rounded-[10px] border border-border bg-surface-menu">
              {(hits.data ?? []).map((hit) => (
                <button
                  key={hit.symbol}
                  type="button"
                  onClick={() => submit(hit.symbol)}
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors hover:bg-foreground/[0.05]"
                >
                  <Figure className="text-control font-medium">{hit.symbol}</Figure>
                  <span className="min-w-0 truncate text-micro text-ink-5">
                    {hit.organ_name}
                  </span>
                  <Figure className="ml-auto shrink-0 text-micro text-ink-6">
                    {hit.exchange}
                  </Figure>
                </button>
              ))}
            </div>
          )}

          {add.isError && (
            <p role="alert" className="px-1 pt-1.5 text-micro text-destructive">
              {add.error instanceof Error ? add.error.message : "Không thêm được mã."}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-fit gap-px px-2.5">
        {entries.map((entry) => {
          const quote = quotes.get(entry.symbol)
          const changePct = quote?.change_pct ?? null
          const active = state.contextSymbol === entry.symbol
          // The sentence rather than the state's name: "Pending" beside a grey
          // dot tells a reader who already sees a grey dot nothing, and the two
          // waits this distinguishes are both `pending`.
          const condition = stateSentence(entry.state, tradingDay, entry.failure)

          return (
            <div
              key={entry.symbol}
              className="group/row relative flex items-center gap-2 rounded-lg transition-colors hover:bg-foreground/[0.04]"
            >
              {active && (
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 rounded-lg bg-primary/[0.08] shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.22)]"
                />
              )}
              <button
                type="button"
                onClick={() => dispatch({ type: "context-symbol", symbol: entry.symbol })}
                aria-pressed={active}
                className="relative flex min-w-0 flex-1 items-center gap-2 py-1.5 pl-2 text-left"
              >
                <i
                  role="img"
                  aria-label={condition}
                  title={condition}
                  className={cn("block size-1.5 shrink-0 rounded-full", STATE_DOT[entry.state])}
                />
                <Figure className="w-10 shrink-0 text-control font-medium">
                  {entry.symbol}
                </Figure>
                <Figure className="text-meta text-ink-3">{price(quote?.match_price)}</Figure>
                <Figure className={cn("ml-auto text-micro", deltaClass(changePct))}>
                  {signedPercent(changePct)}
                </Figure>
                {entry.unread && (
                  <i
                    aria-label="Có phân tích chưa đọc"
                    className="block size-1.5 shrink-0 rounded-full bg-primary"
                  />
                )}
              </button>
              <IconButton
                label={`Bỏ theo dõi ${entry.symbol}`}
                size="sm"
                onClick={() => remove.mutate(entry.symbol)}
                className="mr-1.5 size-[18px] rounded-[5px] text-ink-6 opacity-0 hover:bg-destructive/[0.16] hover:text-destructive focus-visible:opacity-100 group-hover/row:opacity-100"
              >
                <X className="size-3" strokeWidth={2} />
              </IconButton>
            </div>
          )
        })}

        {rail.isPending && <QuietLine>Đang tải danh sách…</QuietLine>}
        {!rail.isPending && entries.length === 0 && (
          <QuietLine>Chưa có mã nào. Thêm mã để VisgniteAI theo dõi mỗi phiên.</QuietLine>
        )}
      </div>
    </>
  )
}
