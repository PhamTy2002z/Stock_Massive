"use client"

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react"
import { useQuery } from "@tanstack/react-query"
import { Maximize2, Search, X } from "lucide-react"

import { usePriceHistory } from "@/hooks/use-price-history"
import { useMarketStockDetail } from "@/hooks/use-market-monitor"
import { useMarketIndices } from "@/hooks/use-market-indices"
import { useSectorPerformance } from "@/hooks/use-sector-performance"
import { useVN30Overview } from "@/hooks/use-vn30-overview"
import {
  fetchSectorPeers,
  fetchStockDetail,
  searchStocks,
  type SectorPeersResponse,
  type StockDetail,
} from "@/lib/api"
import { formatVolume } from "@/lib/format"
import { STALE_TIME } from "@/lib/query-config"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"
import { useMarketMonitorUrlState } from "@/lib/market-monitor/url-state"
import type { MarketStockDetailResponse } from "@/lib/market-monitor/api"
import {
  directionClass as monitorDirectionClass,
  formatMetric as formatMonitorMetric,
  formatMonitorTime,
  issueText,
  signedMetric as signedMonitorMetric,
} from "@/components/market-monitor/monitor-primitives"
import { Button } from "@/components/ui/button"

import { NewsSourcesTab } from "./news-sources"
import {
  Bar,
  deltaClass,
  Eyebrow,
  Figure,
  IconButton,
  PanelCard,
  peakChange,
  price,
  sectorTint,
  signedPercent,
} from "./primitives"
import { maxInspectorWidth, useInspectorDrag, useShell } from "./shell-state"
import { SourcesTab } from "./sources-tab"

/**
 * The right-hand inspector: the session, or one symbol, beside the conversation.
 *
 * It is a panel rather than a page on purpose. Everything in it is context for
 * the question being asked in the column to its left, and navigating away to
 * read a price would lose the conversation that needed it. That is also why it
 * resizes: how much room the market deserves against the conversation is the
 * reader's call, not the layout's.
 */
export function Inspector() {
  const { state, dispatch, panelWidth } = useShell()
  const onDrag = useInspectorDrag()
  const open = state.inspector !== null
  const compact = state.viewport > 0 && state.viewport < 768
  const closeRef = useRef<HTMLButtonElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const wasOpen = useRef(false)

  useEffect(() => {
    if (open && !wasOpen.current && compact) {
      returnFocusRef.current = document.activeElement as HTMLElement | null
      requestAnimationFrame(() => closeRef.current?.focus())
    }
    if (!open && wasOpen.current && compact) returnFocusRef.current?.focus()
    wasOpen.current = open
  }, [compact, open])

  return (
    <>
    {compact && open && (
      <button
        type="button"
        aria-label="Đóng bảng thông tin"
        onClick={() => dispatch({ type: "close-inspector" })}
        className="fixed inset-0 z-[39] cursor-default bg-background/70"
      />
    )}
    <div
      style={{ width: compact ? "100%" : panelWidth }}
      className={cn(
        "absolute right-0 z-40 overflow-hidden",
        compact
          ? open
            ? "inset-x-0 bottom-0 h-[92dvh] rounded-t-card"
            : "pointer-events-none inset-x-0 bottom-0 h-0"
          : "inset-y-0",
        open && "shadow-panel",
        state.dragging ? "transition-none" : "transition-[width] duration-panel ease-panel",
      )}
    >
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Đổi độ rộng bảng thông tin"
        aria-valuemin={320}
        aria-valuemax={maxInspectorWidth(state.viewport)}
        aria-valuenow={open ? panelWidth : undefined}
        tabIndex={open ? 0 : -1}
        onPointerDown={onDrag}
        onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
          const step = event.shiftKey ? 64 : 24
          let width: number | null = null
          if (event.key === "ArrowLeft") width = panelWidth + step
          if (event.key === "ArrowRight") width = panelWidth - step
          if (event.key === "Home") width = 320
          if (event.key === "End") width = maxInspectorWidth(state.viewport)
          if (width === null) return
          event.preventDefault()
          dispatch({ type: "resize-inspector", width })
        }}
        onDoubleClick={() => dispatch({ type: "reset-inspector-width" })}
        className={cn("absolute inset-y-0 left-0 z-[6] w-[9px] cursor-col-resize items-center justify-center transition-colors hover:bg-primary/[0.16] focus-visible:bg-primary/[0.16] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring", compact ? "hidden" : "flex")}
      >
        <span className="h-8 w-0.5 rounded-pill bg-foreground/[0.16]" />
      </div>

      <aside
        aria-label="Bảng thông tin thị trường"
        role={compact ? "dialog" : undefined}
        aria-modal={compact ? true : undefined}
        aria-hidden={!open}
        onKeyDown={(event) => {
          if (!compact || event.key !== "Tab") return
          const focusable = event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
          )
          if (focusable.length === 0) return
          const first = focusable[0]
          const last = focusable[focusable.length - 1]
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
          if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
        }}
        className={cn(
          "flex h-full w-full flex-col bg-surface-panel transition-opacity duration-panel",
          compact ? "rounded-t-card border-t border-border" : "border-l border-border",
          open ? "opacity-100" : "opacity-0",
        )}
      >
        {compact && <span className="mx-auto mt-2 h-1 w-10 rounded-pill bg-foreground/[0.16]" aria-hidden="true" />}
        <div className="flex flex-none items-center gap-0.5 border-b border-border py-2.5 pl-3.5 pr-2.5">
          <div className="flex gap-0.5">
            <TabButton
              active={state.inspector === "market"}
              onClick={() => dispatch({ type: "open-inspector", tab: "market" })}
            >
              Thị trường
            </TabButton>
            <TabButton
              active={state.inspector === "symbol"}
              onClick={() => dispatch({ type: "open-inspector", tab: "symbol" })}
            >
              Chi tiết <Figure>{state.selected.symbol}</Figure>
            </TabButton>
            {/* Only while an answer is being examined, for the same reason as
                the news tab: without one it is a tab onto nothing. */}
            {state.sourcesMessageId !== null && (
              <TabButton
                active={state.inspector === "sources"}
                onClick={() =>
                  dispatch({
                    type: "open-sources",
                    messageId: state.sourcesMessageId as number,
                  })
                }
              >
                Nguồn
              </TabButton>
            )}
            {/* Only while an article is open: the tab describes that article, so
                without one it would be a tab onto nothing. */}
            {state.newsArticle !== null && (
              <TabButton
                active={state.inspector === "news"}
                onClick={() => dispatch({ type: "open-inspector", tab: "news" })}
              >
                Nguồn tin
              </TabButton>
            )}
          </div>
          <IconButton
            label={state.inspectorWide ? "Thu hẹp bảng" : "Mở rộng bảng"}
            size="sm"
            onClick={() => dispatch({ type: "toggle-inspector-wide" })}
            className={cn("ml-auto", compact && "hidden")}
          >
            <Maximize2 className="size-4" strokeWidth={1.6} />
          </IconButton>
          <IconButton
            ref={closeRef}
            label="Đóng bảng"
            size="sm"
            onClick={() => dispatch({ type: "close-inspector" })}
          >
            <X className="size-4" strokeWidth={1.8} />
          </IconButton>
        </div>

        {/* Not on the sources tab: that tab is about one answer, and a symbol
            search above it would offer to navigate away from the thing the
            reader opened it to check. */}
        {open && state.inspector !== "sources" && <SymbolSearch />}

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-3.5">
          {open && (state.inspector === "market" ? (
            <MarketTab />
          ) : state.inspector === "news" ? (
            <NewsSourcesTab />
          ) : state.inspector === "sources" ? (
            <SourcesTab />
          ) : (
            <SymbolTab />
          ))}
        </div>
      </aside>
    </div>
    </>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-lg px-2.5 py-1.5 text-control transition-colors",
        active ? "bg-foreground/[0.07] text-foreground" : "text-ink-3 hover:bg-foreground/[0.05]",
      )}
    >
      {children}
    </button>
  )
}

/** Jump the panel to any listed symbol without leaving the conversation. */
function SymbolSearch() {
  const { dispatch } = useShell()
  const [term, setTerm] = useState("")

  const trimmed = term.trim()
  const hits = useQuery({
    queryKey: queryKeys.stockSearch(trimmed, 5),
    queryFn: () => searchStocks(trimmed, 5),
    enabled: trimmed.length > 0,
    staleTime: STALE_TIME.STATIC,
  })

  function pick(symbol: string, name: string | null, exchange: string | null) {
    dispatch({
      type: "select-symbol",
      selected: { symbol, name: name ?? symbol, exchange: exchange ?? "—" },
      open: true,
    })
    setTerm("")
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    const first = hits.data?.[0]
    if (event.key === "Enter" && first) {
      event.preventDefault()
      pick(first.symbol, first.organ_name, first.exchange)
    }
    if (event.key === "Escape") setTerm("")
  }

  return (
    <div className="relative flex-none border-b border-border px-3.5 py-2.5">
      <div className="flex items-center gap-2 rounded-[10px] border border-border bg-surface-sunken px-2.5 py-1.5">
        <Search className="size-[15px] shrink-0 text-ink-5" strokeWidth={1.6} />
        <input
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onKeyDown={onKeyDown}
          aria-label="Tìm mã, ngành, chỉ số"
          placeholder="Tìm mã, ngành, chỉ số"
          className="min-w-0 flex-1 border-0 bg-transparent text-control text-foreground outline-none placeholder:text-ink-6"
        />
        {trimmed && (
          <IconButton label="Xoá tìm kiếm" size="sm" onClick={() => setTerm("")} className="size-5">
            <X className="size-3" strokeWidth={2.2} />
          </IconButton>
        )}
      </div>

      {(hits.data ?? []).length > 0 && (
        <div className="absolute inset-x-3.5 top-[52px] z-[5] animate-vg-row-in overflow-hidden rounded-xl border border-border bg-surface-menu shadow-menu">
          {(hits.data ?? []).map((hit) => (
            <button
              key={hit.symbol}
              type="button"
              onClick={() => pick(hit.symbol, hit.organ_name, hit.exchange)}
              className="flex w-full items-center gap-2.5 px-2.5 py-2 text-left transition-colors hover:bg-foreground/[0.05]"
            >
              <Figure className="w-[74px] shrink-0 text-control font-medium">{hit.symbol}</Figure>
              <span className="min-w-0 flex-1 truncate text-meta text-ink-4">{hit.organ_name}</span>
              <Figure className="shrink-0 text-micro text-ink-6">{hit.exchange}</Figure>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Market

/**
 * The session, from the top down.
 *
 * The headline sentence is assembled from figures that are on this API and from
 * nothing else — the index's own move, and the sectors at each end of the day.
 * It states them; it does not interpret them. The two panels that would need
 * breadth and per-symbol index contribution say plainly that they are drawn
 * from the reference.
 */
function MarketTab() {
  const { dispatch } = useShell()
  const indices = useMarketIndices()
  const sectors = useSectorPerformance()
  const vn30 = useVN30Overview()

  const headline = indices.data?.[0] ?? null
  const ranked = [...(sectors.data?.sectors ?? [])].sort((a, b) => b.change_pct - a.change_pct)
  const best = ranked[0]
  const worst = ranked[ranked.length - 1]
  const sectorPeak = peakChange(sectors.data?.sectors ?? [])

  return (
    <div>
      {headline && (
        <div
          className={cn(
            "mb-4 rounded-card border bg-surface-sunken p-3.5",
            headline.changePercent >= 0 ? "border-positive/25" : "border-negative/25",
          )}
        >
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-[7px] px-2 py-1 text-micro font-medium",
                headline.changePercent >= 0
                  ? "bg-positive/[0.16] text-positive"
                  : "bg-negative/[0.16] text-negative",
              )}
            >
              {headline.changePercent >= 0 ? "Phiên tăng" : "Phiên giảm"}
            </span>
          </div>
          <p className="mt-2.5 text-pretty text-row leading-relaxed text-ink-2">
            {headline.name} {headline.change >= 0 ? "tăng" : "mất"}{" "}
            <b className="font-semibold">
              {Math.abs(headline.change).toLocaleString("vi-VN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              điểm ({signedPercent(headline.changePercent)})
            </b>
            {best && worst && best.icb_code !== worst.icb_code && (
              <>
                {/* "Dẫn dắt" only when the sector actually rose. On a red day
                    the best sector is the one that held up, and calling it a
                    leader would read as a claim the figures do not make. */}
                . {best.change_pct >= 0 ? "Dẫn dắt" : "Giữ giá tốt nhất"} là {best.icb_name} (
                {signedPercent(best.change_pct, 1)}), {worst.change_pct <= 0 ? "kéo lùi" : "tăng chậm nhất"} là{" "}
                {worst.icb_name} ({signedPercent(worst.change_pct, 1)}).
              </>
            )}
          </p>
        </div>
      )}

      <SectionHeading>Chỉ số thị trường</SectionHeading>
      <div className="mt-2.5 grid grid-cols-2 gap-2.5">
        {(indices.data ?? []).map((index) => (
          <PanelCard key={index.symbol}>
            <div className="text-micro font-semibold tracking-[0.06em] text-ink-4">
              {index.name}
            </div>
            <Figure className="mt-1 block text-[1.22rem] font-semibold tracking-[-0.02em]">
              {index.value.toLocaleString("vi-VN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </Figure>
            <Figure className={cn("mt-0.5 block text-meta", deltaClass(index.changePercent))}>
              {index.changePercent >= 0 ? "▲" : "▼"}{" "}
              {Math.abs(index.change).toLocaleString("vi-VN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              ({signedPercent(index.changePercent)})
            </Figure>
          </PanelCard>
        ))}
      </div>

      <SectionHeading className="mt-5">Nhiệt độ ngành</SectionHeading>
      <div className="mt-2.5 grid gap-[7px] [grid-template-columns:repeat(auto-fit,minmax(104px,1fr))]">
        {(sectors.data?.sectors ?? []).map((sector) => (
          <div
            key={sector.icb_code}
            title={sector.icb_name}
            className="min-w-0 rounded-[10px] px-2.5 py-2 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.05)]"
            style={{ backgroundColor: sectorTint(sector.change_pct, sectorPeak) }}
          >
            <div className="truncate text-micro text-ink-2">{sector.icb_name}</div>
            <Figure
              className={cn("mt-1 block text-control font-semibold", deltaClass(sector.change_pct))}
            >
              {signedPercent(sector.change_pct, 1)}
            </Figure>
          </div>
        ))}
      </div>

      <SectionHeading className="mt-5">Tổng quan VN30</SectionHeading>
      <div className="mt-2.5 overflow-hidden rounded-xl border border-border bg-surface-sunken">
        {(vn30.data?.stocks ?? []).slice(0, 8).map((stock) => (
          <button
            key={stock.symbol}
            type="button"
            onClick={() =>
              dispatch({
                type: "select-symbol",
                selected: { symbol: stock.symbol, name: stock.company_name, exchange: "HOSE" },
                open: true,
              })
            }
            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-control transition-colors hover:bg-foreground/[0.035]"
          >
            <Figure className="w-11 shrink-0 font-medium">{stock.symbol}</Figure>
            <span className="min-w-0 flex-1 truncate text-meta text-ink-4">
              {stock.company_name}
            </span>
            <Figure>{price(stock.price)}</Figure>
            <Figure className={cn("w-[60px] shrink-0 text-right", deltaClass(stock.change_pct))}>
              {signedPercent(stock.change_pct)}
            </Figure>
          </button>
        ))}
        {(vn30.data?.stocks ?? []).length === 0 && (
          <p className="px-3 py-6 text-center text-meta text-ink-6">
            {vn30.isPending ? "Đang tải…" : "Chưa có dữ liệu VN30."}
          </p>
        )}
      </div>
      {(vn30.data?.stocks ?? []).length > 8 && (
        <p className="mt-2 text-meta text-ink-6">
          1–8 trên {vn30.data?.stocks.length} cổ phiếu · bấm một mã để xem chi tiết
        </p>
      )}
    </div>
  )
}

/** Per-symbol index contribution. No endpoint computes it; the reference's own. */
// ---------------------------------------------------------------------------
// Symbol

function SymbolTab() {
  const { state, dispatch } = useShell()
  const symbol = state.selected.symbol
  const monitorUrl = useMarketMonitorUrlState()

  const detail = useQuery<StockDetail>({
    queryKey: queryKeys.stockDetail(symbol),
    queryFn: () => fetchStockDetail(symbol),
    staleTime: STALE_TIME.REALTIME,
  })
  const peers = useQuery<SectorPeersResponse>({
    queryKey: queryKeys.sectorPeers(symbol),
    queryFn: () => fetchSectorPeers(symbol, 6),
    staleTime: STALE_TIME.STATIC,
    retry: false,
  })
  const history = usePriceHistory(symbol, "1D")
  const monitor = useMarketStockDetail(
    symbol,
    { exchange: monitorUrl.state.exchange, asOf: monitorUrl.state.asOf },
    state.view === "board",
  )

  const data = detail.data
  const changePct = data?.change_pct ?? null

  if (detail.isError) {
    return (
      <div className="rounded-card border border-border bg-surface-sunken p-4">
        <p className="text-meta leading-relaxed text-ink-4">
          Chưa đọc được dữ liệu của {symbol}. Kết nối có thể đang gián đoạn hoặc nguồn dữ liệu chưa phản hồi.
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={detail.isFetching}
          onClick={() => void detail.refetch()}
          className="mt-3"
        >
          {detail.isFetching ? "Đang thử lại…" : "Thử lại"}
        </Button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <Figure className="text-[1.3rem] font-semibold tracking-[-0.02em]">{symbol}</Figure>
          </div>
          <div className="mt-1 text-meta text-ink-4">
            {data?.company_name ?? state.selected.name}
            {data?.exchange ? ` · ${data.exchange}` : ""}
          </div>
        </div>
        <div className="ml-auto shrink-0 text-right">
          <Figure className={cn("block text-[1.3rem] font-semibold tracking-[-0.02em]", deltaClass(changePct))}>
            {price(data?.price)}
          </Figure>
          <Figure className={cn("block text-meta", deltaClass(changePct))}>
            {changePct === null ? "—" : changePct >= 0 ? "▲" : "▼"} {price(data?.change)} (
            {signedPercent(changePct)})
          </Figure>
        </div>
      </div>

      <div className="mt-3 flex gap-4 font-mono text-meta">
        <span className="text-ink-6">
          Trần <span className="text-ceiling">{price(data?.ceiling)}</span>
        </span>
        <span className="text-ink-6">
          TC <span className="text-reference">{price(data?.ref_price)}</span>
        </span>
        <span className="text-ink-6">
          Sàn <span className="text-floor">{price(data?.floor)}</span>
        </span>
      </div>

      <PanelCard className="mt-3.5">
        <div className="flex justify-between gap-4 text-meta">
          <span className="text-ink-6">Diễn biến trong phiên</span>
          <Figure className="text-ink-4">1D</Figure>
        </div>
        <Sparkline
          points={(history.data ?? []).map((point) => point.close)}
          reference={data?.ref_price ?? null}
          rising={(changePct ?? 0) >= 0}
        />
        {history.isPending && (
          <p className="pt-2 text-micro text-ink-6">Đang tải chuỗi giá…</p>
        )}
      </PanelCard>

      {state.view === "board" && (
        <MonitorSymbolEvidence
          data={monitor.data}
          pending={monitor.isPending}
          error={monitor.isError}
          retry={() => void monitor.refetch()}
        />
      )}

      <div className="mt-3 grid gap-2.5">
        <PanelCard>
          <Eyebrow>Vùng giá 52 tuần</Eyebrow>
          <div className="mt-2 flex justify-between font-mono text-meta">
            <span>{price(data?.low_52_week)}</span>
            <span className="text-ink-4">hiện tại {price(data?.price)}</span>
            <span>{price(data?.high_52_week)}</span>
          </div>
          <div className="mt-2">
            <Bar
              width={`${rangePosition(data)}%`}
              delay={150}
              className="bg-[linear-gradient(90deg,hsl(var(--negative)),hsl(var(--reference)),hsl(var(--primary)))]"
            />
          </div>
          {data?.high_52_week && data.price && (
            <p className="mt-2 text-meta text-ink-6">
              Thấp hơn đỉnh 52T{" "}
              {(((data.high_52_week - data.price) / data.high_52_week) * 100)
                .toFixed(1)
                .replace(".", ",")}
              %
            </p>
          )}
        </PanelCard>

        <div className="grid grid-cols-2 gap-2.5">
          <PanelCard>
            <Eyebrow>Thanh khoản</Eyebrow>
            <Figure className="mt-1.5 block text-[1.05rem] font-semibold">
              {data?.volume ? formatVolume(data.volume) : "—"}
            </Figure>
            <p className="text-micro text-ink-6">
              {data?.avg_volume_52_week && data.volume
                ? `${Math.round((data.volume / data.avg_volume_52_week) * 100)}% BQ 52T`
                : "—"}
            </p>
          </PanelCard>
          <PanelCard>
            <Eyebrow>P/E</Eyebrow>
            <Figure className="mt-1.5 block text-[1.05rem] font-semibold">
              {data?.pe ? data.pe.toFixed(2).replace(".", ",") : "—"}
            </Figure>
            <p className="text-micro text-ink-6">
              {peers.data?.sector_median.pe
                ? `trung vị ngành ${peers.data.sector_median.pe.toFixed(2).replace(".", ",")}`
                : "—"}
            </p>
          </PanelCard>
        </div>

        <PanelCard>
          <Eyebrow>Cùng ngành{peers.data ? ` · ${peers.data.icb_name}` : ""}</Eyebrow>
          <div className="mt-2 grid grid-cols-fit gap-0.5">
            {(peers.data?.peers ?? [])
              .filter((peer) => peer.symbol !== symbol)
              .slice(0, 4)
              .map((peer) => (
                <button
                  key={peer.symbol}
                  type="button"
                  onClick={() =>
                    dispatch({
                      type: "select-symbol",
                      selected: {
                        symbol: peer.symbol,
                        name: peer.company_name ?? peer.symbol,
                        exchange: state.selected.exchange,
                      },
                      open: true,
                    })
                  }
                  className="flex items-center gap-2.5 rounded-md py-1 text-left text-control transition-colors hover:bg-foreground/[0.04]"
                >
                  <Figure className="w-11 shrink-0">{peer.symbol}</Figure>
                  <span className="text-meta text-ink-4">
                    P/E {peer.pe ? peer.pe.toFixed(2).replace(".", ",") : "—"}
                  </span>
                  <Figure className={cn("ml-auto shrink-0", deltaClass(peer.premium_pe))}>
                    {peer.premium_pe === null ? "—" : signedPercent(peer.premium_pe, 1)}
                  </Figure>
                </button>
              ))}
            {peers.isError && (
              <p className="py-1 text-meta text-ink-6">Chưa có dữ liệu so sánh ngành.</p>
            )}
            {peers.isPending && <p className="py-1 text-meta text-ink-6">Đang tải…</p>}
          </div>
        </PanelCard>
      </div>

      <div className="mt-3.5 flex gap-2">
        <Button
          type="button"
          size="action"
          onClick={() => {
            dispatch({ type: "context-symbol", symbol })
            dispatch({
              type: "ask",
              text: `${symbol} đang rẻ hay đắt so với nhóm cùng ngành?`,
            })
          }}
          className="flex-1 px-3"
        >
          Hỏi VisgniteAI về {symbol}
        </Button>
        {/* No alerting resource exists. Inert rather than absent, so the panel
            keeps the reference's shape. */}
        <Button
          type="button"
          variant="outline"
          size="action"
          disabled
          title="Sắp có"
          className="px-3 disabled:pointer-events-auto"
        >
          Cảnh báo giá · Sắp ra mắt
        </Button>
      </div>
    </div>
  )
}

function MonitorSymbolEvidence({
  data,
  pending,
  error,
  retry,
}: {
  data: MarketStockDetailResponse | undefined
  pending: boolean
  error: boolean
  retry: () => void
}) {
  if (pending) {
    return <div role="status" className="mt-3.5 h-32 animate-pulse rounded-card bg-foreground/[0.045]"><span className="sr-only">Đang tải bằng chứng Market Monitor</span></div>
  }
  if (error || !data) {
    return <div className="mt-3.5 rounded-card bg-surface-sunken p-3 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]"><p className="text-meta text-ink-4">Chưa đọc được bằng chứng xu hướng, dòng tiền và định giá.</p><button type="button" onClick={retry} className="mt-2 min-h-10 text-meta font-medium text-ink-2 underline decoration-foreground/25 underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Thử lại phần này</button></div>
  }
  const stock = data.stock
  const valuation = data.evidence.valuation
  return <div className="mt-3.5 grid gap-2.5">
    <PanelCard>
      <h3 className="text-control font-medium text-ink-2">Xu hướng</h3>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {[1, 5, 20].map((window) => { const metric = stock.metrics[`return_${window}d_pct`]; return <div key={window}><p className="text-micro text-ink-6">{window} phiên</p><Figure className={cn("mt-1 block text-meta font-semibold", monitorDirectionClass(metric?.value))}>{signedMonitorMetric(metric)}</Figure></div> })}
      </div>
      <p className="mt-2 border-t border-hairline pt-2 text-micro text-ink-5">{[20, 50, 200].map((window) => { const value = stock.trend[`above_ma${window}`]?.value; return value === null || value === undefined ? `MA${window} —` : `${value ? "Trên" : "Dưới"} MA${window}` }).join(" · ")}</p>
    </PanelCard>
    <PanelCard>
      <h3 className="text-control font-medium text-ink-2">Dòng tiền</h3>
      <div className="mt-2 grid grid-cols-2 gap-3"><div><p className="text-micro text-ink-6">Khối ngoại 20 phiên</p><Figure className={cn("mt-1 block text-meta font-semibold", monitorDirectionClass(stock.metrics.foreign_net_20d_vnd?.value))}>{signedMonitorMetric(stock.metrics.foreign_net_20d_vnd)}</Figure></div><div><p className="text-micro text-ink-6">Khối ngoại / ADTV</p><Figure className="mt-1 block text-meta font-semibold">{formatMonitorMetric(stock.metrics.foreign_flow_over_adtv)}</Figure></div></div>
    </PanelCard>
    <PanelCard>
      <h3 className="text-control font-medium text-ink-2">Định giá</h3>
      <div className="mt-2 grid grid-cols-2 gap-3"><div><p className="text-micro text-ink-6">P/E</p><Figure className="mt-1 block text-meta font-semibold">{formatMonitorMetric(stock.metrics.pe)}</Figure></div><div><p className="text-micro text-ink-6">P/B</p><Figure className="mt-1 block text-meta font-semibold">{formatMonitorMetric(stock.metrics.pb)}</Figure></div></div>
      <p className="mt-2 text-micro text-ink-6">{valuation ? `FiinQuant · phiên ${valuation.session_date}` : "Chưa có quan sát định giá dương hợp lệ."}</p>
    </PanelCard>
    <PanelCard>
      <h3 className="text-control font-medium text-ink-2">Nguồn và phương pháp</h3>
      <p className="mt-1.5 text-micro leading-relaxed text-ink-5">As-of {formatMonitorTime(data.meta.as_of)} · {data.meta.coverage.evaluated}/{data.meta.coverage.eligible} mã · {data.meta.state}</p>
      <ul className="mt-2 grid gap-1 text-micro text-ink-5">{data.meta.sources.map((source) => <li key={source.source}>{source.source} · {formatMonitorTime(source.effective_at)}{source.stale ? " · cũ" : ""}</li>)}</ul>
      {data.meta.issues.length > 0 && <p className="mt-2 text-micro leading-relaxed text-ink-6">{data.meta.issues.map(issueText).join(" · ")}</p>}
      <p className="mt-2 break-words font-mono text-micro text-ink-6">{Object.values(data.meta.method_versions).join(" · ")}</p>
    </PanelCard>
  </div>
}

/** Where today's price sits inside the 52-week band, as a percentage. */
function rangePosition(data: StockDetail | undefined): number {
  if (!data?.price || !data.low_52_week || !data.high_52_week) return 0
  const span = data.high_52_week - data.low_52_week
  if (span <= 0) return 0
  return Math.max(0, Math.min(100, ((data.price - data.low_52_week) / span) * 100))
}

/**
 * The session's shape, drawn from the closes the history endpoint returned.
 *
 * A path rather than a charting library: this is one series with no axes, no
 * tooltip and no legend, and pulling Recharts into a 90px box would ship a
 * renderer to draw a line. The reference price is the dashed rule, because the
 * only question this chart answers is which side of it the day spent.
 */
function Sparkline({
  points,
  reference,
  rising,
}: {
  points: number[]
  reference: number | null
  rising: boolean
}) {
  const path = useMemo(() => {
    if (points.length < 2) return null
    const low = Math.min(...points, reference ?? Infinity)
    const high = Math.max(...points, reference ?? -Infinity)
    const span = high - low || 1
    const x = (index: number) => (index / (points.length - 1)) * 320
    const y = (value: number) => 92 - ((value - low) / span) * 84

    return {
      line: points.map((value, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(1)} ${y(value).toFixed(1)}`).join(" "),
      referenceY: reference === null ? null : y(reference),
    }
  }, [points, reference])

  if (path === null) {
    return (
      <div className="mt-2 flex h-[100px] items-center justify-center text-micro text-ink-6">
        Chưa đủ dữ liệu để vẽ.
      </div>
    )
  }

  return (
    <svg
      viewBox="0 0 320 100"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="mt-2 block h-[100px] w-full"
    >
      {path.referenceY !== null && (
        <line
          x1="0"
          y1={path.referenceY}
          x2="320"
          y2={path.referenceY}
          stroke="hsl(var(--reference))"
          strokeWidth="1"
          strokeDasharray="3 4"
          opacity=".55"
        />
      )}
      <path
        d={path.line}
        fill="none"
        stroke={rising ? "hsl(var(--positive))" : "hsl(var(--negative))"}
        strokeWidth="1.7"
        strokeLinejoin="round"
        strokeLinecap="round"
        className="animate-vg-draw-line"
      />
    </svg>
  )
}

function SectionHeading({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-baseline gap-2", className)}>
      <span className="text-[0.95rem] text-ink-1">{children}</span>
    </div>
  )
}
