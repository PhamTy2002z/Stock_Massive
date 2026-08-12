"use client"

/** PROTOTYPE — shared content, not shared layout, for issue #22. */

import * as React from "react"
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  Clock3,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ARTIFACTS } from "../../analysis-artifact/_components/fixtures"
import { VariantD } from "../../analysis-artifact/_components/variant-d"
import {
  STATE_LABELS,
  THREADS,
  WATCHLIST,
  type HarnessState,
  type WatchSymbol,
} from "./fixtures"

export function ThreadList({ compact = false }: { compact?: boolean }) {
  return (
    <div className="space-y-1">
      {THREADS.map((thread) => (
        <button
          key={thread.id}
          type="button"
          className={cn(
            "group w-full rounded-lg text-left transition-colors hover:bg-secondary/70",
            compact ? "px-2 py-1.5" : "px-2.5 py-2",
            thread.active && "bg-secondary"
          )}
        >
          <span className="flex items-center justify-between gap-2">
            <span className="truncate text-[12px] font-medium">{thread.title}</span>
            <span className="shrink-0 text-[9px] text-muted-foreground">{thread.time}</span>
          </span>
          {!compact && (
            <>
              <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">
                {thread.preview}
              </span>
              <span className="mt-1 flex items-center justify-between">
                <span className="flex gap-1">
                  {thread.symbols.map((symbol) => (
                    <code key={symbol} className="rounded bg-card px-1 py-px text-[9px]">
                      {symbol}
                    </code>
                  ))}
                </span>
                <Trash2 className="h-3 w-3 opacity-0 text-muted-foreground group-hover:opacity-100" />
              </span>
            </>
          )}
        </button>
      ))}
    </div>
  )
}

export function symbolForState(state: HarnessState) {
  if (state === "deep") return "HPG"
  if (state === "pending") return "FPT"
  if (state === "artifact") return "MWG"
  return "VCB"
}

export function Watchlist({
  horizontal = false,
  activeSymbol = "VCB",
}: {
  horizontal?: boolean
  activeSymbol?: string
}) {
  if (horizontal) {
    return (
      <div className="flex min-w-0 gap-1.5 overflow-x-auto pb-1">
        {WATCHLIST.map((item) => (
          <WatchChip key={item.symbol} item={item} active={item.symbol === activeSymbol} />
        ))}
        <button type="button" className="flex shrink-0 items-center gap-1 rounded-full border border-dashed border-border px-2.5 py-1 text-[10px] text-muted-foreground">
          <Plus className="h-3 w-3" /> Add
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {WATCHLIST.map((item) => (
        <button
          key={item.symbol}
          type="button"
          className={cn(
            "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-secondary/70",
            item.symbol === activeSymbol && "bg-secondary"
          )}
        >
          <span className="relative font-mono text-[12px] font-semibold">
            {item.symbol}
            {item.unread && <span className="absolute -right-2 -top-0.5 h-1.5 w-1.5 rounded-full bg-primary" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className={cn("block text-[10px] font-medium", toneClass(item.tone))}>
              {item.verdict}
            </span>
            <span className="block text-[9px] text-muted-foreground">phiên {item.session}</span>
          </span>
          {item.verdict === "Pending" ? (
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3 w-3 -rotate-90 text-muted-foreground" />
          )}
        </button>
      ))}
    </div>
  )
}

function WatchChip({ item, active }: { item: WatchSymbol; active: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "relative flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-[10px]",
        active && "border-foreground/40 bg-secondary"
      )}
    >
      <strong className="font-mono">{item.symbol}</strong>
      <span className={toneClass(item.tone)}>{item.verdict}</span>
      {item.unread && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
    </button>
  )
}

function toneClass(tone: WatchSymbol["tone"]) {
  if (tone === "positive") return "text-emerald-700 dark:text-emerald-400"
  if (tone === "negative") return "text-rose-700 dark:text-rose-400"
  if (tone === "waiting") return "text-amber-700 dark:text-amber-400"
  return "text-muted-foreground"
}

export function Conversation({ state, roomy = false }: { state: HarnessState; roomy?: boolean }) {
  if (state === "empty") return <EmptyConversation />
  const symbol = symbolForState(state)

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-[13px] font-semibold">
              {state === "deep" ? "HPG từ Stock 360" : state === "pending" ? "FPT — Analysis mới" : state === "artifact" ? "MWG: tín hiệu sau phiên" : "VCB sau phiên 11/08"}
            </span>
            <code className="rounded bg-secondary px-1.5 py-0.5 text-[9px]">{symbol}</code>
          </div>
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            {STATE_LABELS[state]} · lưu trong Thread
          </p>
        </div>
        <button type="button" className="rounded-full p-1.5 text-muted-foreground hover:bg-secondary">
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={cn("mx-auto w-full px-4 py-5", roomy ? "max-w-[58rem]" : "max-w-[48rem]")}>
          {state === "deep" && <DeepLinkPrelude />}
          {state === "pending" ? <PendingAnalysis /> : <ConversationTurns state={state} />}
        </div>
      </div>
      <Composer symbol={symbol} pending={state === "pending"} />
    </div>
  )
}

function ConversationTurns({ state }: { state: HarnessState }) {
  return (
    <>
      <div className="mb-4 flex justify-end">
        <div className="max-w-[82%] rounded-2xl rounded-br-md bg-secondary px-3.5 py-2 text-[13px]">
          {state === "artifact" ? "Phân tích MWG hôm nay giúp tôi." : "Dòng tiền VCB hôm nay có gì đáng chú ý?"}
        </div>
      </div>

      {state === "tool" && (
        <div className="mb-3 rounded-lg border border-border bg-card">
          <details open>
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[11px] text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span className="font-medium text-foreground">Đang đọc dữ liệu đã lưu</span>
              <span>· foreign_flow</span>
              <ChevronDown className="ml-auto h-3.5 w-3.5" />
            </summary>
            <div className="border-t border-border px-3 py-2 font-mono text-[10px] text-muted-foreground">
              symbol=VCB · window_days=30 · store-only
            </div>
          </details>
        </div>
      )}

      {state === "artifact" ? (
        <div className="my-3">
          <VariantD artifact={ARTIFACTS.MWG} />
        </div>
      ) : (
        <div className="text-[13px] leading-relaxed text-foreground/90">
          <p>
            Dòng ngoại mua ròng nhẹ trong bốn phiên, nhưng quy mô vẫn nhỏ so với thanh khoản bình quân. Đây là lực đỡ, chưa phải thay đổi chế độ.
          </p>
          {state === "tool" ? (
            <p className="mt-3 text-muted-foreground">
              Tôi đang đối chiếu thêm độ bền của chuỗi mua ròng
              <span className="ml-1 inline-flex gap-0.5 align-middle">
                <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.2s]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.1s]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-current" />
              </span>
            </p>
          ) : (
            <div className="mt-3 flex items-center gap-2 text-[10px] text-muted-foreground">
              <Check className="h-3 w-3" /> 3 registered fields · dữ liệu phiên 11/08
            </div>
          )}
        </div>
      )}
    </>
  )
}

function PendingAnalysis() {
  return (
    <div className="mx-auto max-w-lg py-10 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
      <h2 className="mt-4 text-sm font-semibold">Đang tạo Analysis cho FPT</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-[12px] leading-relaxed text-muted-foreground">
        Snapshot phiên 11/08 đã sẵn sàng. Bạn có thể tiếp tục hỏi trong Thread này; Analysis sẽ xuất hiện tại đây khi hoàn tất.
      </p>
      <div className="mx-auto mt-5 max-w-sm space-y-2 text-left">
        <ProgressStep done label="Assemble registered evidence" />
        <ProgressStep active label="Generate fixed artifact" />
        <ProgressStep label="Validate and publish" />
      </div>
      <div className="mt-5 rounded-lg border border-border bg-card px-3 py-2 text-left text-[10px] text-muted-foreground">
        Analysis gần nhất: <strong className="text-foreground">Hold · phiên 08/08</strong>
      </div>
    </div>
  )
}

function ProgressStep({ label, done, active }: { label: string; done?: boolean; active?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className={cn("flex h-5 w-5 items-center justify-center rounded-full border border-border", (done || active) && "border-foreground/30 bg-secondary")}>
        {done ? <Check className="h-3 w-3" /> : active ? <Loader2 className="h-3 w-3 animate-spin" /> : <Clock3 className="h-3 w-3 text-muted-foreground" />}
      </span>
      <span className={cn(!done && !active && "text-muted-foreground")}>{label}</span>
    </div>
  )
}

function DeepLinkPrelude() {
  return (
    <div className="mb-5 flex items-start gap-3 rounded-xl border border-primary/25 bg-primary/[0.06] px-3 py-2.5">
      <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="text-[12px] font-medium">Tiếp tục từ Stock 360 · HPG</p>
        <p className="mt-0.5 text-[10.5px] text-muted-foreground">
          Alpha Desk đã mang mã HPG vào Thread mới, không tự thêm vào Watchlist.
        </p>
      </div>
    </div>
  )
}

function EmptyConversation() {
  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-6">
        <div className="w-full max-w-lg text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-foreground text-background">
            <Sparkles className="h-5 w-5" />
          </div>
          <h1 className="mt-4 text-lg font-semibold tracking-tight">Bắt đầu với một mã bạn quan tâm</h1>
          <p className="mx-auto mt-2 max-w-sm text-[12px] leading-relaxed text-muted-foreground">
            Watchlist đang trống. Bạn vẫn có thể hỏi về bất kỳ mã nào trong Universe; chỉ những mã thêm vào Watchlist mới được phân tích lại mỗi phiên.
          </p>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {["Phân tích VCB", "So sánh FPT và CMG", "Tìm mã ngân hàng", "Dòng ngoại mua gì?"].map((item) => (
              <button key={item} type="button" className="rounded-xl border border-border bg-card px-3 py-2.5 text-left text-[11px] hover:bg-secondary/50">
                {item}
              </button>
            ))}
          </div>
        </div>
      </div>
      <Composer symbol="" />
    </div>
  )
}

function Composer({ symbol, pending }: { symbol: string; pending?: boolean }) {
  return (
    <div className="shrink-0 border-t border-border bg-card px-3 py-3">
      <div className="mx-auto flex max-w-[48rem] items-end gap-2 rounded-xl border border-input bg-background px-3 py-2 shadow-sm">
        <button type="button" className="mb-0.5 rounded-md p-1 text-muted-foreground hover:bg-secondary">
          <Plus className="h-4 w-4" />
        </button>
        <textarea
          rows={1}
          placeholder={pending ? "Bạn vẫn có thể hỏi tiếp…" : symbol ? `Hỏi tiếp về ${symbol}…` : "Hỏi Alpha Desk…"}
          className="max-h-28 min-h-6 flex-1 resize-none bg-transparent text-[12px] outline-none placeholder:text-muted-foreground"
        />
        <button type="button" className="rounded-lg bg-foreground p-1.5 text-background">
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

export function RailHeading({ children, action }: { children: React.ReactNode; action?: "plus" | "search" }) {
  return (
    <div className="flex items-center justify-between gap-2 px-2.5 pb-2 pt-3">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{children}</span>
      {action && (
        <button type="button" className="rounded p-1 text-muted-foreground hover:bg-secondary">
          {action === "plus" ? <Plus className="h-3.5 w-3.5" /> : <Search className="h-3.5 w-3.5" />}
        </button>
      )}
    </div>
  )
}

export function MobileRailMenu({ label, kind }: { label: string; kind: "threads" | "watchlist" }) {
  return (
    <details className="relative lg:hidden">
      <summary className="flex cursor-pointer list-none items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-[10px]">
        {kind === "threads" ? <MessageSquare className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}
        {label}
        <ChevronDown className="h-3 w-3" />
      </summary>
      <div className="absolute left-0 top-full z-30 mt-1 w-64 rounded-xl border border-border bg-popover p-2 shadow-xl">
        {kind === "threads" ? <ThreadList /> : <Watchlist />}
      </div>
    </details>
  )
}
