"use client"

import { useState } from "react"
import { useVolumeAnalysis } from "@/hooks/use-volume-analysis"
import { VolumeAnomalyChart } from "./volume-anomaly-chart"
import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import type { VolumeTimeSlot } from "@/lib/api"

interface VolumeTabContentProps {
  symbol: string
}

const baselines = [10, 20, 60]

const legend = [
  { color: "bg-[#c7c7cc]", label: "Bình thường" },
  { color: "bg-reference", label: "Tăng cao 1,5–2×" },
  { color: "bg-caution", label: "Cao 2–3×" },
  { color: "bg-negative", label: "Rất cao >3×" },
]

const compact = (value: number) =>
  value >= 1_000_000
    ? `${(value / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })}M`
    : `${(value / 1_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}K`

const ratio = (value: number) =>
  `${value.toLocaleString("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}×`

function Chip({
  label,
  isActive,
  onClick,
}: {
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isActive}
      className={cn(
        "rounded-full text-[13px] leading-[1.29] tracking-[-0.208px]",
        "transition-transform duration-150 active:scale-95",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isActive
          ? "border-2 border-interactive-strong px-[13px] py-1.5 font-semibold"
          : "border border-border px-3.5 py-[7px] text-muted-foreground hover:text-foreground"
      )}
    >
      {label}
    </button>
  )
}

function Stat({
  label,
  value,
  meta,
  tone,
}: {
  label: string
  value: string
  meta: string
  tone?: "negative"
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "text-2xl font-semibold leading-[1.2] tracking-[-0.374px] tabular-nums",
          tone === "negative" && "text-negative"
        )}
      >
        {value}
      </span>
      <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
        {meta}
      </span>
    </div>
  )
}

/** Slots the analysis flagged as anything above normal. */
const flaggedSlots = (slots: VolumeTimeSlot[]) =>
  slots.filter((s) => s.anomaly_level !== "normal")

export function VolumeTabContent({ symbol }: VolumeTabContentProps) {
  const [days, setDays] = useState(20)
  const { data, refetch, isFetching } = useVolumeAnalysis(symbol, days)

  const slots = data?.time_slots ?? []

  if (slots.length === 0) {
    return (
      <div className="min-w-0 rounded-[18px] border border-border bg-card p-[18px]">
        <div className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Chưa có dữ liệu khối lượng
        </div>
        <p className="mt-1 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          Dữ liệu khối lượng trong ngày chưa được thu thập cho {symbol}.
        </p>
      </div>
    )
  }

  const peak = slots.reduce((best, slot) =>
    slot.current_volume > best.current_volume ? slot : best
  )
  const flagged = flaggedSlots(slots)
  const severe = flagged.filter((s) => s.anomaly_level === "very_high")
  const baseline = slots.reduce((sum, s) => sum + s.avg_volume, 0) / slots.length

  return (
    <div className="min-w-0 rounded-[18px] border border-border bg-card p-[18px]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
            Bất thường khối lượng
          </div>
          <div className="mt-1 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
            Nến 5 phút · so với trung bình cùng khung giờ {days} phiên
            {data?.latest_date ? ` · phiên ${data.latest_date}` : ""}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {baselines.map((value) => (
            <Chip
              key={value}
              label={`${value} phiên`}
              isActive={days === value}
              onClick={() => setDays(value)}
            />
          ))}
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            title="Làm mới"
            className="flex size-9 items-center justify-center rounded-full text-interactive transition-[background-color,transform] duration-150 hover:bg-muted active:scale-95 disabled:cursor-progress"
          >
            <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
            <span className="sr-only">Làm mới dữ liệu khối lượng</span>
          </button>
        </div>
      </div>

      <div className="mt-4">
        <VolumeAnomalyChart
          data={slots}
          symbol={data!.symbol}
          daysAnalyzed={data!.days_analyzed}
          latestDate={data!.latest_date}
        />
      </div>

      <div className="mt-3.5 flex flex-wrap gap-4 border-t border-[hsl(var(--hairline))] pt-3.5 text-[13px] leading-[1.43] tracking-[-0.208px]">
        {legend.map((item) => (
          <span key={item.label} className="flex items-center gap-[7px]">
            <span className={cn("size-2 rounded-sm", item.color)} />
            {item.label}
          </span>
        ))}
        <span className="flex items-center gap-[7px] text-interactive">
          <span className="h-0 w-3.5 border-t-2 border-dashed border-interactive" />
          Trung bình {days} phiên
        </span>
      </div>

      <div className="mt-3.5 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3.5 border-t border-[hsl(var(--hairline))] pt-3.5">
        <Stat
          label="Cao nhất trong phiên"
          value={compact(peak.current_volume)}
          meta={`${peak.time_label} · ${ratio(peak.volume_ratio)} trung bình`}
          tone="negative"
        />
        <Stat
          label="Bất thường phát hiện"
          value={String(flagged.length)}
          meta={
            flagged.length
              ? `${severe.length} nến vượt 3× · còn lại 1,5–3×`
              : "Không có nến vượt ngưỡng"
          }
          tone={flagged.length ? "negative" : undefined}
        />
        <Stat
          label="Trung bình 5 phút"
          value={compact(baseline)}
          meta={`Baseline ${days} phiên`}
        />
      </div>
    </div>
  )
}
