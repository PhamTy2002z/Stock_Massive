"use client"

import { AlertTriangle } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { useSymbolSnapshot } from "@/hooks/use-symbol-snapshot"
import { formatDataAge } from "@/lib/format"
import { formatVietnamDate, formatVietnamTime } from "@/lib/market-session"
import { cn } from "@/lib/utils"
import type {
  FundamentalSnapshotData,
  MarketSnapshotData,
  ReferenceSnapshotData,
  SnapshotSection,
  SnapshotSectionMeta,
  SymbolSnapshot,
  ValuationSnapshotData,
} from "@/lib/api"
import { SurfaceCard } from "./ui-kit"

/**
 * What the Collector holds for one symbol, with the age of every part of it.
 *
 * This is the only surface on the page fed from the store rather than from a
 * provider inside the request, so it is also the only one that can say which
 * session its numbers belong to. That is the whole point of showing it: the
 * figures elsewhere on the page are whatever the provider answered a moment
 * ago, while these are a session, dated, from a named source.
 */

const DASH = "—"

const SHARE_TYPE_LABELS: Record<string, string> = {
  outstanding: "Lưu hành",
  listed: "Niêm yết",
  issued: "Đã phát hành",
}

const decimal = (value: number) =>
  value.toLocaleString("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })

const whole = (value: number) => value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })

/** Money in VND, in the unit a Vietnamese reader quotes it in. */
function formatVnd(value: number | null): string {
  if (value === null) return DASH
  const sign = value < 0 ? "-" : ""
  const magnitude = Math.abs(value)
  if (magnitude >= 1e12) return `${sign}${decimal(magnitude / 1e12)} nghìn tỷ`
  if (magnitude >= 1e9) return `${sign}${decimal(magnitude / 1e9)} tỷ`
  if (magnitude >= 1e6) return `${sign}${decimal(magnitude / 1e6)} triệu`
  return `${sign}${whole(magnitude)} đ`
}

const formatPrice = (value: number | null) => (value === null ? DASH : whole(value))

/**
 * A quantity of shares, in the same unit vocabulary as the money beside it.
 *
 * The app-wide M/K ladder covers a session's volume but not ownership — VCB has
 * 8.36 billion shares listed, and "8355.7M" is a number nobody reads. Rather
 * than run two vocabularies in one panel, every quantity here takes the
 * Vietnamese ladder, which is also what the profile sidebar on this page uses.
 */
function formatShares(value: number | null): string {
  if (value === null) return DASH
  if (value >= 1e9) return `${decimal(value / 1e9)} tỷ`
  if (value >= 1e6) return `${decimal(value / 1e6)} triệu`
  if (value >= 1e3) return `${decimal(value / 1e3)} nghìn`
  return whole(value)
}

const formatRatio = (value: number | null) =>
  value === null
    ? DASH
    : value.toLocaleString("vi-VN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** One label and its figure, or a dash where the store has nothing. */
interface Figure {
  label: string
  value: string
}

function marketFigures(data: MarketSnapshotData): Figure[] {
  // bu/sd are the one pair whose absence has a known cause: FiinQuant appends
  // the session's bar before splitting its active flow, so the collector stores
  // the gap rather than the zeros the provider sends. Saying "chưa công bố"
  // keeps that distinct from a figure this system never collects.
  const activeFlow =
    data.active_buy_volume === null && data.active_sell_volume === null
      ? "Chưa công bố"
      : `${formatShares(data.active_buy_volume)} / ${formatShares(data.active_sell_volume)}`

  return [
    { label: "Đóng cửa", value: formatPrice(data.last_price) },
    { label: "Trần / sàn", value: `${formatPrice(data.ceiling_price)} / ${formatPrice(data.floor_price)}` },
    { label: "Khối lượng", value: formatShares(data.volume) },
    { label: "Giá trị giao dịch", value: formatVnd(data.total_value_vnd) },
    { label: "Mua / bán chủ động", value: activeFlow },
    {
      label: "Khối ngoại mua / bán",
      value: `${formatVnd(data.foreign_buy_value_vnd)} / ${formatVnd(data.foreign_sell_value_vnd)}`,
    },
    { label: "Khối ngoại ròng", value: formatVnd(data.foreign_net_value_vnd) },
    { label: "Vốn hoá", value: formatVnd(data.market_cap_vnd) },
  ]
}

function valuationFigures(data: ValuationSnapshotData): Figure[] {
  return [
    { label: "P/E", value: formatRatio(data.provider_pe) },
    { label: "P/B", value: formatRatio(data.provider_pb) },
  ]
}

function referenceFigures(data: ReferenceSnapshotData): Figure[] {
  return [
    ...data.shares.map((share) => ({
      // An unmapped share type is shown as the provider named it rather than
      // dropped: a count without its meaning is worse than an odd label.
      label: SHARE_TYPE_LABELS[share.share_type] ?? share.share_type,
      value: formatShares(share.value),
    })),
    { label: "Room ngoại còn lại", value: formatShares(data.current_foreign_room) },
    { label: "Room ngoại tối đa", value: formatShares(data.total_foreign_room) },
  ]
}

function fundamentalFigures(data: FundamentalSnapshotData): Figure[] {
  // No period row: the statement's own period is what the provenance line
  // stamps, so repeating it here would be the same date twice.
  return [
    {
      label: "LNST 12 tháng",
      value: formatVnd(data.trailing_12_month_net_income_vnd),
    },
    { label: "Vốn chủ sở hữu", value: formatVnd(data.parent_equity_vnd) },
  ]
}

/** What this part is dated by, how old it is, and who published it. */
function Provenance({ meta, stampLabel }: { meta: SnapshotSectionMeta; stampLabel: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] leading-[1.29] text-muted-foreground">
      <span className="rounded-full border border-border px-2 py-0.5 font-medium text-foreground">
        {meta.source}
      </span>
      <span>
        {stampLabel} {formatVietnamDate(meta.effective_at)}
      </span>
      <span aria-hidden>·</span>
      <span>{formatDataAge(meta.age_seconds)} trước</span>
      <span aria-hidden>·</span>
      {/* Age counts from the session, so it says nothing about when the
          Collector last ran. Both facts are needed: one to judge the number,
          the other to judge the system. */}
      <span>
        thu lúc {formatVietnamTime(new Date(meta.observed_at))}{" "}
        {formatVietnamDate(meta.observed_at)}
      </span>
      {meta.stale && (
        <span className="flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 font-medium text-destructive">
          <AlertTriangle aria-hidden className="size-3.5" />
          Quá cũ
        </span>
      )}
    </div>
  )
}

function CapabilityBlock<TData>({
  title,
  section,
  figures,
  /** What `effective_at` names for this capability: a session, or a period. */
  stampLabel = "Phiên",
}: {
  title: string
  section: SnapshotSection<TData> | null
  figures: (data: TData) => Figure[]
  stampLabel?: string
}) {
  return (
    <div className="border-t border-border pt-3.5 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-sm font-semibold leading-[1.29] tracking-[-0.208px]">{title}</h3>
        {section ? (
          <Provenance meta={section} stampLabel={stampLabel} />
        ) : (
          // Absent is not the same as empty: the symbol is watched, this part of
          // it simply has not been collected yet.
          <span className="text-[13px] leading-[1.29] text-muted-foreground">Chưa thu thập</span>
        )}
      </div>

      {section && (
        <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
          {figures(section.data).map((figure) => (
            <div key={figure.label} className="min-w-0">
              <dt className="truncate text-xs text-muted-foreground">{figure.label}</dt>
              <dd className="mt-0.5 truncate text-sm font-semibold tabular-nums">
                {figure.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

function PanelShell({
  symbol,
  children,
  className,
}: {
  symbol: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <SurfaceCard className={className}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-base font-semibold leading-[1.25] tracking-[-0.31px]">
          Dữ liệu đã thu thập
        </h2>
        <span className="text-[13px] leading-[1.29] text-muted-foreground">{symbol}</span>
      </div>
      {children}
    </SurfaceCard>
  )
}

function Sections({ snapshot }: { snapshot: SymbolSnapshot }) {
  return (
    <div className="mt-3.5 space-y-3.5">
      <CapabilityBlock
        title="Giá & thanh khoản"
        section={snapshot.market}
        figures={marketFigures}
      />
      <CapabilityBlock
        title="Định giá"
        section={snapshot.valuation}
        figures={valuationFigures}
      />
      <CapabilityBlock
        title="Cấu trúc sở hữu"
        section={snapshot.reference}
        figures={referenceFigures}
        // Share counts move on corporate actions, but the Adapter dates them by
        // the day it read them — so this stamp is a reading, not a session.
        stampLabel="Đọc ngày"
      />
      <CapabilityBlock
        title="Báo cáo tài chính"
        section={snapshot.fundamental}
        figures={fundamentalFigures}
        // A statement is dated by the quarter it closes, not by a session.
        stampLabel="Kỳ"
      />
    </div>
  )
}

export function StockSnapshotPanel({
  symbol,
  className,
}: {
  symbol: string
  className?: string
}) {
  const { data } = useSymbolSnapshot(symbol)

  if (data === null) {
    return (
      <PanelShell symbol={symbol} className={className}>
        <p className="mt-2.5 text-[13px] leading-[1.4] text-muted-foreground">
          {symbol} không nằm trong tập mã hệ thống thu thập sau mỗi phiên, nên chưa
          có số liệu nào được lưu kèm tuổi dữ liệu cho mã này.
        </p>
      </PanelShell>
    )
  }

  return (
    <PanelShell symbol={symbol} className={className}>
      <Sections snapshot={data} />
    </PanelShell>
  )
}

export function StockSnapshotPanelSkeleton({ className }: { className?: string }) {
  return (
    <SurfaceCard className={cn("space-y-3.5", className)}>
      <Skeleton className="h-5 w-44" />
      {[1, 2, 3, 4].map((block) => (
        <div key={block} className="space-y-2">
          <Skeleton className="h-4 w-36" />
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
            {[1, 2, 3].map((figure) => (
              <div key={figure}>
                <Skeleton className="h-3 w-20" />
                <Skeleton className="mt-1 h-4 w-16" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </SurfaceCard>
  )
}
