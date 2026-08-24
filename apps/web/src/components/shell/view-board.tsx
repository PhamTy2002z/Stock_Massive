"use client"

import { useMemo, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { indexBySymbol, usePriceBoard } from "@/hooks/use-price-board"
import { useMarketIndices } from "@/hooks/use-market-indices"
import { useSectorPerformance } from "@/hooks/use-sector-performance"
import { useVN30Overview } from "@/hooks/use-vn30-overview"
import type { PriceBoardItem } from "@/lib/api"
import { formatVolume } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

import {
  Bar,
  Card,
  deltaClass,
  Eyebrow,
  Figure,
  peakChange,
  price,
  SampleBadge,
  SampleDataNote,
  sectorTint,
  signedPercent,
} from "./primitives"
import { useShell } from "./shell-state"

/** How many rows one page of the board holds. The reference's own number. */
const PER_PAGE = 15

/**
 * The price board: the whole session on one screen.
 *
 * Four readings of the same moment, in the order a trader asks for them — where
 * the indices closed, how the sectors split, what the constituents did one by
 * one, and who the extremes were. The table is the centre of gravity; the cards
 * around it exist to tell you where to look in it.
 *
 * Three of the panels here are drawn from the reference rather than from this
 * API — breadth, the liquidity split and the foreign net have no endpoint yet —
 * and each one says so on its own face. A placeholder that looked like live
 * data is the one failure mode worth designing against on a surface people make
 * money decisions on.
 */
export function BoardView() {
  const { dispatch } = useShell()
  const indices = useMarketIndices()
  const vn30 = useVN30Overview()
  const sectors = useSectorPerformance()

  const symbols = useMemo(
    () => (vn30.data?.stocks ?? []).map((stock) => stock.symbol),
    [vn30.data],
  )
  const board = usePriceBoard(symbols)
  const quotes = useMemo(() => indexBySymbol(board.data), [board.data])

  const rows = useMemo(
    () =>
      (vn30.data?.stocks ?? []).map((stock) => ({
        symbol: stock.symbol,
        name: stock.company_name,
        quote: quotes.get(stock.symbol) ?? null,
        // The overview's own price is the fallback: the board endpoint may not
        // hold a row for every constituent, and a blank line reads as an outage.
        price: quotes.get(stock.symbol)?.match_price ?? stock.price,
        changePct: quotes.get(stock.symbol)?.change_pct ?? stock.change_pct,
        volume: quotes.get(stock.symbol)?.total_vol ?? stock.volume,
      })),
    [vn30.data, quotes],
  )

  const sectorPeak = useMemo(
    () => peakChange(sectors.data?.sectors ?? []),
    [sectors.data],
  )

  const [page, setPage] = useState(0)
  const pages = Math.max(1, Math.ceil(rows.length / PER_PAGE))
  const from = Math.min(page, pages - 1) * PER_PAGE
  const visible = rows.slice(from, from + PER_PAGE)

  return (
    <div
      onClick={() => dispatch({ type: "overlay", overlay: null })}
      className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-1.5"
    >
      <div className="mx-auto grid max-w-[1180px] gap-3.5">
        <section aria-label="Chỉ số thị trường" className="grid gap-2.5 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
          {(indices.data ?? []).map((index) => (
            <Card key={index.symbol} className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-micro font-semibold tracking-[0.07em] text-ink-4">
                  {index.name}
                </span>
              </div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <Figure
                  className={cn(
                    "text-[1.34rem] font-semibold tracking-[-0.025em]",
                    deltaClass(index.changePercent),
                  )}
                >
                  {index.value.toLocaleString("vi-VN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </Figure>
                <Figure className={cn("text-meta", deltaClass(index.changePercent))}>
                  {index.change >= 0 ? "+" : "−"}
                  {Math.abs(index.change).toLocaleString("vi-VN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}{" "}
                  ({signedPercent(index.changePercent)})
                </Figure>
              </div>
            </Card>
          ))}
          {indices.isPending &&
            Array.from({ length: 4 }, (_, slot) => (
              <Card key={`index-skeleton-${slot}`} className="h-[86px] animate-pulse" >
                <span className="sr-only">Đang tải chỉ số</span>
              </Card>
            ))}
        </section>

        <div className="flex flex-wrap gap-3.5">
          <Card className="min-w-0 flex-[2_1_480px]">
            <div className="flex items-baseline gap-2.5">
              <span className="text-[0.95rem] text-ink-1">Nhiệt độ ngành</span>
              <span className="ml-auto text-micro text-ink-6">% thay đổi bình quân</span>
            </div>
            {/* Every sector, not a top slice: the wall answers how broad the
                session was, and a truncated one answers a different question. */}
            <div className="mt-3 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(112px,1fr))]">
              {(sectors.data?.sectors ?? []).map((sector) => (
                <SectorTile
                  key={sector.icb_code}
                  name={sector.icb_name}
                  changePct={sector.change_pct}
                  peak={sectorPeak}
                />
              ))}
              {sectors.isPending && (
                <p className="col-span-full text-meta text-ink-6">Đang tải ngành…</p>
              )}
              {!sectors.isPending && (sectors.data?.sectors ?? []).length === 0 && (
                <p className="col-span-full text-meta text-ink-6">
                  Chưa có dữ liệu ngành cho phiên này.
                </p>
              )}
            </div>
          </Card>

          <div className="grid min-w-0 flex-[1_1_260px] content-start gap-3.5">
            <LiquidityCard />
            <ForeignFlowCard />
          </div>
        </div>

        <section
          aria-label="Bảng giá VN30"
          className="overflow-hidden rounded-card border border-border bg-surface-raised"
        >
          <div className="flex items-center gap-2.5 border-b border-border px-3.5 py-3">
            <span className="text-[0.95rem] text-ink-1">Bảng giá VN30</span>
            <span className="ml-auto flex gap-3 font-mono text-micro">
              <span className="text-ceiling">trần</span>
              <span className="text-reference">tham chiếu</span>
              <span className="text-floor">sàn</span>
            </span>
          </div>

          <div className="overflow-x-auto table-scroll-container">
            <table className="w-full min-w-[760px] border-collapse text-control">
              <thead>
                <tr>
                  <Th align="left">Mã</Th>
                  <Th>Trần</Th>
                  <Th>TC</Th>
                  <Th>Sàn</Th>
                  <Th>Giá</Th>
                  <Th>%</Th>
                  <Th>Khối lượng</Th>
                  <Th>Giá trị</Th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <BoardRow key={row.symbol} row={row} />
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-3.5 py-8 text-center text-meta text-ink-6">
                      {vn30.isPending ? "Đang tải bảng giá…" : "Chưa có dữ liệu phiên."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {rows.length > 0 && (
            <div className="flex items-center gap-3 border-t border-border px-3.5 py-2.5">
              <span className="text-meta text-ink-6">
                {from + 1}–{Math.min(from + PER_PAGE, rows.length)} trên {rows.length} cổ phiếu
              </span>
              <div className="ml-auto flex items-center gap-2">
                <Figure className="text-meta text-ink-4">
                  Trang {Math.min(page, pages - 1) + 1}/{pages}
                </Figure>
                <PageButton
                  label="Trang trước"
                  disabled={page === 0}
                  onClick={() => setPage((current) => Math.max(0, current - 1))}
                >
                  <ChevronLeft className="size-3.5" strokeWidth={1.9} />
                </PageButton>
                <PageButton
                  label="Trang sau"
                  disabled={page >= pages - 1}
                  onClick={() => setPage((current) => Math.min(pages - 1, current + 1))}
                >
                  <ChevronRight className="size-3.5" strokeWidth={1.9} />
                </PageButton>
              </div>
            </div>
          )}
        </section>

        <Rankings rows={rows} />

        <AskAboutSession />
      </div>
    </div>
  )
}

interface Row {
  symbol: string
  name: string
  quote: PriceBoardItem | null
  price: number | null
  changePct: number | null
  volume: number | null
}

function BoardRow({ row }: { row: Row }) {
  const { dispatch } = useShell()

  function openSymbol() {
    dispatch({
      type: "select-symbol",
      selected: { symbol: row.symbol, name: row.name, exchange: "HOSE" },
      open: true,
    })
  }

  return (
    <tr
      tabIndex={0}
      aria-label={`Mở chi tiết ${row.symbol} — ${row.name}`}
      onClick={openSymbol}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return
        event.preventDefault()
        openSymbol()
      }}
      className="cursor-pointer transition-colors hover:bg-foreground/[0.035] focus-visible:bg-foreground/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
    >
      <td className="border-b border-hairline px-3.5 py-2">
        <Figure className="font-semibold">{row.symbol}</Figure>
        <span className="mt-0.5 block max-w-[180px] truncate text-micro text-ink-6">
          {row.name}
        </span>
      </td>
      <Td className="text-ceiling">{price(row.quote?.ceiling)}</Td>
      <Td className="text-reference">{price(row.quote?.ref_price)}</Td>
      <Td className="text-floor">{price(row.quote?.floor)}</Td>
      <Td className={cn("font-semibold", deltaClass(row.changePct))}>{price(row.price)}</Td>
      <Td className={deltaClass(row.changePct)}>{signedPercent(row.changePct)}</Td>
      <Td className="text-ink-3">{row.volume === null ? "—" : formatVolume(row.volume)}</Td>
      <Td className="pr-3.5 text-ink-3">{compactVnd(row.quote?.total_val ?? null)}</Td>
    </tr>
  )
}

function Th({ children, align = "right" }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-hairline px-2.5 py-2 text-eyebrow font-semibold uppercase text-ink-6",
        align === "left" ? "pl-3.5 text-left" : "text-right",
      )}
    >
      {children}
    </th>
  )
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <td className={cn("border-b border-hairline px-2.5 py-2 text-right font-mono tabular-nums", className)}>
      {children}
    </td>
  )
}

function PageButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex size-7 items-center justify-center rounded-lg border border-border text-ink-4 transition-colors hover:bg-foreground/[0.06] hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  )
}

/**
 * One sector, tinted by how far it moved against the loudest move of the day.
 *
 * The figure is stated in text as well — colour never carries the reading on
 * its own, which is also what keeps the wall legible to anyone who cannot
 * separate the two hues.
 */
function SectorTile({
  name,
  changePct,
  peak,
}: {
  name: string
  changePct: number
  peak: number
}) {
  return (
    <div
      title={name}
      className="min-w-0 rounded-[10px] p-2.5 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.05)]"
      style={{ backgroundColor: sectorTint(changePct, peak) }}
    >
      <div className="truncate text-meta text-ink-2">{name}</div>
      <Figure className={cn("mt-1 block text-row font-semibold", deltaClass(changePct))}>
        {signedPercent(changePct, 1)}
      </Figure>
    </div>
  )
}

/**
 * Market-wide turnover, and how it splits across the three exchanges.
 *
 * No endpoint serves this: the API aggregates per sector and per symbol, and
 * nothing rolls those up to a session total. The shape is the reference's; the
 * figures are placeholders, and the card says so.
 */
function LiquidityCard() {
  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>Thanh khoản toàn thị trường</Eyebrow>
        <SampleBadge />
      </div>
      <Figure className="mt-1.5 block text-[1.4rem] font-semibold tracking-[-0.02em]">
        24.680 tỷ
      </Figure>
      <div className="mt-2.5 flex justify-between border-t border-hairline py-1.5 text-meta">
        <span className="text-ink-6">HOSE</span>
        <Figure>21.410 tỷ</Figure>
      </div>
      <div className="flex justify-between py-1.5 text-meta">
        <span className="text-ink-6">HNX · UPCOM</span>
        <Figure>3.270 tỷ</Figure>
      </div>
      <div className="flex justify-between pb-2.5 pt-1.5 text-meta">
        <span className="text-ink-6">So với BQ 20 phiên</span>
        <Figure className="text-positive">1,18×</Figure>
      </div>
      <SampleDataNote>API chưa tổng hợp thanh khoản toàn thị trường.</SampleDataNote>
    </Card>
  )
}

const SAMPLE_FOREIGN = [
  { symbol: "VHM", value: -412 },
  { symbol: "VIC", value: -286 },
  { symbol: "FPT", value: 118 },
  { symbol: "STB", value: 96 },
  { symbol: "HPG", value: -74 },
]

/** Foreign net flow. No endpoint yet; the reference's own figures, marked. */
function ForeignFlowCard() {
  const peak = Math.max(...SAMPLE_FOREIGN.map((row) => Math.abs(row.value)))

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>Khối ngoại ròng</Eyebrow>
        <SampleBadge />
      </div>
      <Figure className="mt-1.5 block text-[1.4rem] font-semibold tracking-[-0.02em] text-negative">
        −1.240 tỷ
      </Figure>
      <div className="mt-2.5 grid grid-cols-fit gap-1.5">
        {SAMPLE_FOREIGN.map((row, position) => (
          <div key={row.symbol} className="flex items-center gap-2.5 text-meta">
            <Figure className="w-10 shrink-0">{row.symbol}</Figure>
            <span className="min-w-0 flex-1">
              <Bar
                width={`${Math.round((Math.abs(row.value) / peak) * 100)}%`}
                delay={position * 60}
                className={row.value > 0 ? "bg-positive" : "bg-negative"}
              />
            </span>
            <Figure
              className={cn("w-16 shrink-0 text-right", deltaClass(row.value))}
            >
              {row.value > 0 ? "+" : "−"}
              {Math.abs(row.value)} tỷ
            </Figure>
          </div>
        ))}
      </div>
      <div className="pt-2.5">
        <SampleDataNote>API chưa phục vụ dòng tiền khối ngoại.</SampleDataNote>
      </div>
    </Card>
  )
}

/**
 * Who led and who dragged, derived from the board rather than from a list.
 *
 * Three rankings over the same rows, which is why they are computed here and
 * not fetched: the board is already on screen, and a second request asking the
 * API to sort it would be able to disagree with what the reader is looking at.
 */
function Rankings({ rows }: { rows: Row[] }) {
  const ranked = useMemo(() => {
    const withChange = rows.filter((row) => row.changePct !== null)
    const byChange = [...withChange].sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0))
    const byVolume = [...rows]
      .filter((row) => row.volume !== null)
      .sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0))

    return [
      { title: "Tăng mạnh", unit: "% phiên", rows: byChange.slice(0, 5), kind: "change" as const },
      {
        title: "Giảm sâu",
        unit: "% phiên",
        rows: byChange.slice(-5).reverse(),
        kind: "change" as const,
      },
      {
        title: "Thanh khoản dẫn dắt",
        unit: "khối lượng",
        rows: byVolume.slice(0, 5),
        kind: "volume" as const,
      },
    ]
  }, [rows])

  const { dispatch } = useShell()

  if (rows.length === 0) return null

  return (
    <div className="grid gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(250px,1fr))]">
      {ranked.map((group) => (
        // `min-w-0`, or a grid item sizes to its widest company name and the
        // figure beside it slides off the card's right edge.
        <Card key={group.title} className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-row text-ink-1">{group.title}</span>
            <span className="ml-auto text-micro text-ink-6">{group.unit}</span>
          </div>
          <div className="mt-2.5 grid grid-cols-fit gap-0.5">
            {group.rows.map((row) => (
              <button
                key={row.symbol}
                type="button"
                onClick={() =>
                  dispatch({
                    type: "select-symbol",
                    selected: { symbol: row.symbol, name: row.name, exchange: "HOSE" },
                    open: true,
                  })
                }
                className="flex items-center gap-2.5 rounded-[7px] p-1.5 text-left text-control transition-colors hover:bg-foreground/[0.04]"
              >
                <Figure className="w-11 shrink-0 font-medium">{row.symbol}</Figure>
                <span className="min-w-0 flex-1 truncate text-micro text-ink-4">{row.name}</span>
                <Figure
                  className={cn(
                    "shrink-0",
                    group.kind === "change" ? deltaClass(row.changePct) : "text-ink-3",
                  )}
                >
                  {group.kind === "change"
                    ? signedPercent(row.changePct)
                    : row.volume === null
                      ? "—"
                      : formatVolume(row.volume)}
                </Figure>
              </button>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}

/** The board's one way back into the conversation. */
function AskAboutSession() {
  const { dispatch } = useShell()

  return (
    <div className="flex items-center gap-3 rounded-card border border-primary/[0.18] bg-surface-raised px-4 py-3.5">
      <span className="text-pretty text-control text-ink-4">
        Muốn hiểu vì sao thị trường đi như phiên nay? Đưa bảng giá này vào hội thoại để
        VisgniteAI phân tích.
      </span>
      <Button
        type="button"
        size="action"
        onClick={() =>
          dispatch({
            type: "ask",
            text: "Phiên hôm nay thị trường diễn biến ra sao? Nhóm nào dẫn dắt và nhóm nào kéo VN-INDEX xuống?",
          })
        }
        className="ml-auto shrink-0"
      >
        Hỏi VisgniteAI
      </Button>
    </div>
  )
}

/**
 * A session's traded value, in the unit a Vietnamese reader expects.
 *
 * The board endpoint reports value in **millions of VND** — the same unit
 * `StockDetail.trading_value` documents — so a billion is a thousand of them.
 * Stated as a named constant rather than an inline `1e3` because the whole
 * reading of this column depends on it, and a wrong order of magnitude on a
 * trading screen is worse than no column at all.
 */
const MILLIONS_PER_BILLION = 1_000

function compactVnd(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—"
  const billions = value / MILLIONS_PER_BILLION
  if (Math.abs(billions) >= 1) {
    return `${billions.toLocaleString("vi-VN", { maximumFractionDigits: 0 })} tỷ`
  }
  return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })} tr`
}
