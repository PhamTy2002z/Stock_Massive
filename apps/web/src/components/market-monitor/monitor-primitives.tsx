"use client"

import { AlertTriangle, RefreshCw } from "lucide-react"

import type { MetricValue, MonitorMeta, MonitorState } from "@/lib/market-monitor/api"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

const STATE_COPY: Record<MonitorState, string> = {
  complete: "Đầy đủ",
  partial: "Dữ liệu một phần",
  stale: "Dữ liệu cũ",
  disconnected: "Realtime gián đoạn",
  unavailable: "Chưa có dữ liệu",
}

const ISSUE_COPY: Record<string, string> = {
  realtime_projection_unavailable: "Chưa có phép chiếu realtime cho phạm vi này.",
  foreign_flow_not_stored: "Chưa có dữ liệu giao dịch khối ngoại trong kho lưu trữ.",
  declining_zero: "Không có mã giảm để tính tỷ lệ tăng/giảm.",
  realtime_scope_empty: "Phạm vi realtime hiện chưa có mã đủ điều kiện.",
  unavailable: "Nguồn chưa cung cấp đủ bằng chứng để tính chỉ số này.",
  insufficient_valuation_history: "Cần tối thiểu 20 phiên định giá để tính phân vị.",
}

export function issueText(issue: string): string {
  return ISSUE_COPY[issue] ?? issue.replaceAll("_", " ")
}

export function formatMonitorTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.valueOf())) return "—"
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(parsed)
}

export function formatMetric(metric: MetricValue | undefined, digits = 1): string {
  const value = metric?.value
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  const unit = metric?.unit
  if (unit === "VND") {
    const absolute = Math.abs(value)
    if (absolute >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} nghìn tỷ`
    if (absolute >= 1_000_000_000) return `${(value / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`
    if (absolute >= 1_000_000) return `${(value / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} triệu`
    return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })} đ`
  }
  if (unit === "%") return `${value.toLocaleString("vi-VN", { maximumFractionDigits: digits })}%`
  if (unit === "ratio") return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 2 })}×`
  if (unit === "symbol") return value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })
  return value.toLocaleString("vi-VN", { maximumFractionDigits: digits })
}

export function signedMetric(metric: MetricValue | undefined, digits = 1): string {
  if (metric?.value === null || metric?.value === undefined) return "—"
  return `${metric.value > 0 ? "+" : ""}${formatMetric(metric, digits)}`
}

export function directionClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-reference"
  return value > 0 ? "text-positive" : "text-negative"
}

export function CoverageLine({ meta, updating = false }: { meta: MonitorMeta; updating?: boolean }) {
  return (
    <p className="font-mono text-micro tabular-nums text-ink-5" aria-live="polite">
      {updating ? "Đang cập nhật · " : ""}
      {formatMonitorTime(meta.as_of)} · {meta.coverage.evaluated}/{meta.coverage.eligible} mã · {STATE_COPY[meta.state]}
      {meta.realtime_coverage ? ` · RT ${meta.realtime_coverage.evaluated}/${meta.realtime_coverage.eligible}` : ""}
    </p>
  )
}

export function MonitorStateNotice({ meta }: { meta: MonitorMeta }) {
  if (meta.state === "complete") return null
  const copy =
    meta.state === "partial"
      ? meta.realtime_coverage && meta.realtime_coverage.state !== "complete"
        ? `EOD vẫn hiển thị ${meta.coverage.evaluated}/${meta.coverage.eligible} mã; realtime mới đánh giá ${meta.realtime_coverage.evaluated}/${meta.realtime_coverage.eligible} mã.`
        : `Đang hiển thị ${meta.coverage.evaluated}/${meta.coverage.eligible} mã đủ bằng chứng.`
      : meta.state === "stale"
        ? `Bằng chứng gần nhất tại ${formatMonitorTime(meta.as_of)}; số liệu vẫn được giữ để đối chiếu.`
        : meta.state === "disconnected"
          ? "Kết nối DNSE realtime đang gián đoạn; dữ liệu EOD vẫn được giữ nguyên và tách biệt."
          : "Chưa có mã nào đủ bằng chứng cho phạm vi đã chọn."
  return (
    <div
      role={meta.state === "unavailable" ? "alert" : "status"}
      className="flex gap-2.5 rounded-card bg-surface-sunken px-3.5 py-3 text-meta text-ink-3 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.08)]"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-reference" aria-hidden="true" />
      <div>
        <p className="font-medium text-ink-2">{STATE_COPY[meta.state]}</p>
        <p className="mt-0.5 leading-relaxed">{copy}</p>
        {meta.issues.length > 0 && <p className="mt-1 text-ink-5">{issueText(meta.issues[0])}</p>}
      </div>
    </div>
  )
}

export function LensLoading() {
  return (
    <div role="status" aria-label="Đang tải Market Monitor" className="grid gap-[18px]">
      <div className="h-28 animate-pulse rounded-card bg-foreground/[0.055]" />
      <div className="grid gap-3 md:grid-cols-3">
        <div className="h-40 animate-pulse rounded-card bg-foreground/[0.04] md:col-span-2" />
        <div className="h-40 animate-pulse rounded-card bg-foreground/[0.04]" />
      </div>
      <span className="sr-only">Đang tải dữ liệu thị trường</span>
    </div>
  )
}

export function LensError({ retry, message }: { retry: () => void; message?: string }) {
  return (
    <div role="alert" className="rounded-card bg-surface-raised p-5 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.09)]">
      <p className="text-row font-medium text-ink-1">Không đọc được Market Monitor</p>
      <p className="mt-1 max-w-[68ch] text-meta leading-relaxed text-ink-4">
        {message ?? "Kết nối hoặc nguồn dữ liệu chưa phản hồi. Các góc nhìn khác vẫn có thể sử dụng."}
      </p>
      <Button type="button" size="sm" onClick={retry} className="mt-3 gap-2">
        <RefreshCw className="size-3.5" aria-hidden="true" /> Thử lại
      </Button>
    </div>
  )
}

export function LensEmpty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-card bg-surface-raised px-4 py-8 text-center text-meta text-ink-4 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]">{children}</p>
}

export function SectionHeading({ children, detail }: { children: React.ReactNode; detail?: React.ReactNode }) {
  return (
    <div className="mb-2.5 flex items-baseline gap-3">
      <h2 className="text-[0.95rem] font-medium text-ink-1">{children}</h2>
      {detail && <span className="ml-auto text-meta text-ink-6">{detail}</span>}
    </div>
  )
}

export function EvidencePanel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn("rounded-card bg-surface-raised p-3.5 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]", className)}>{children}</section>
}

export function MetricReading({ label, metric, signed = false, className }: { label: string; metric: MetricValue | undefined; signed?: boolean; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <p className="text-meta text-ink-5">{label}</p>
      <p className={cn("mt-1 font-mono text-[1.08rem] font-semibold tabular-nums text-ink-1", signed && directionClass(metric?.value))}>
        {signed ? signedMetric(metric) : formatMetric(metric)}
      </p>
      {metric?.value === null && metric.issues[0] && <p className="mt-1 text-micro leading-snug text-ink-6">{issueText(metric.issues[0])}</p>}
    </div>
  )
}

export function BreadthBar({ advancing, declining, unchanged }: { advancing: number | null; declining: number | null; unchanged: number | null }) {
  if (advancing === null || declining === null || unchanged === null) return <p className="text-meta text-ink-6">Chưa đủ dữ liệu để dựng tỷ trọng.</p>
  const total = advancing + declining + unchanged
  if (total === 0) return <p className="text-meta text-ink-6">Chưa đủ dữ liệu để dựng tỷ trọng.</p>
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-pill bg-foreground/[0.06]" aria-hidden="true">
        <span className="bg-positive" style={{ width: `${(advancing / total) * 100}%` }} />
        <span className="bg-reference" style={{ width: `${(unchanged / total) * 100}%` }} />
        <span className="bg-negative" style={{ width: `${(declining / total) * 100}%` }} />
      </div>
      <p className="sr-only">{advancing} mã tăng, {unchanged} mã không đổi, {declining} mã giảm.</p>
    </div>
  )
}

export function RotationLabel({ value }: { value: string }) {
  const labels: Record<string, string> = {
    leading: "Dẫn dắt",
    improving: "Cải thiện",
    weakening: "Suy yếu",
    lagging: "Tụt hậu",
    unavailable: "Chưa phân loại",
  }
  return <span className="text-meta text-ink-4">{labels[value] ?? value}</span>
}
