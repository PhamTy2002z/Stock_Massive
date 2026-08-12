"use client"

/**
 * PROTOTYPE — throwaway. Issue #21. Variant C — "Narrative + evidence pills".
 *
 * The answer this variant argues for: the artifact is *written*, and every
 * figure inside the writing is a pill you can interrogate — unit, kind,
 * interpretation, staleness on hover. The ledger of registered fields is a rail,
 * not the body.
 *
 * Note the deliberate boundary-push: this is the only variant where the model
 * orders the *paragraphs* by emphasis (lead axis first) rather than keeping the
 * four axes in fixed DOM order. That is the thing to accept or reject — if
 * "fixed template" forbids it, this variant dies or reverts to fixed order.
 */

import * as React from "react"
import { ArrowUpRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { ExpandButton, ExpandOverlay, useExpanded } from "./expand"
import {
  type AnalysisArtifact,
  type AxisSection,
  type Figure,
  VERDICT_LABEL,
  byEmphasis,
  formatValue,
  formatVnd,
} from "./fixtures"

export const VARIANT_C_NAME = "Narrative + pills"

export function VariantC({ artifact }: { artifact: AnalysisArtifact }) {
  const { expanded, setExpanded } = useExpanded()
  const sections = byEmphasis(artifact)
  const cited = new Set(artifact.citedFieldIds)

  const prose = (
    <div className="space-y-4">
      <p className="text-[15px] font-medium leading-snug text-foreground">
        {artifact.verdictLine}
      </p>

      <p className="text-[13.5px] leading-relaxed text-foreground/90">{artifact.thesis}</p>

      <PriceZoneSentence artifact={artifact} />

      {sections.map((s) => (
        <AxisParagraph key={s.axis} section={s} cited={cited} />
      ))}

      {artifact.news.length > 0 && (
        <div className="space-y-1 border-l-2 border-border pl-3">
          {artifact.news.map((n) => (
            <p key={n.title} className="text-[12px] leading-snug text-muted-foreground">
              <span className="font-mono">{n.publishedAt}</span> · {n.title}{" "}
              <span className="italic">({n.source})</span>
            </p>
          ))}
        </div>
      )}
    </div>
  )

  const footer = (
    <div className="mt-5 space-y-2 border-t border-border pt-3">
      <a
        href={`/analytics/deep-dive?symbol=${artifact.symbol}`}
        className="inline-flex items-center gap-1 text-[12px] font-medium text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
      >
        Số liệu đầy đủ và biểu đồ: Stock 360 · {artifact.symbol}
        <ArrowUpRight className="h-3 w-3" />
      </a>
      <p className="text-[10px] leading-relaxed text-muted-foreground">
        {artifact.disclaimer}
      </p>
    </div>
  )

  return (
    <>
      <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
        <TopLine artifact={artifact} onExpand={() => setExpanded(true)} />
        {prose}
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-secondary/50 px-3 py-2">
          <span className="text-[11px] text-muted-foreground">
            Nhận định tựa trên{" "}
            <strong className="font-semibold text-foreground">
              {artifact.citedFieldIds.length} registered field
            </strong>{" "}
            — mở rộng để xem sổ chỉ số.
          </span>
        </div>
        {footer}
      </div>

      {expanded && (
        <ExpandOverlay onClose={() => setExpanded(false)}>
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="px-6 py-5">
              <TopLine artifact={artifact} />
              {prose}
              {footer}
            </div>
            <Ledger artifact={artifact} cited={cited} />
          </div>
        </ExpandOverlay>
      )}
    </>
  )
}

function TopLine({
  artifact,
  onExpand,
}: {
  artifact: AnalysisArtifact
  onExpand?: () => void
}) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div className="text-[11px] leading-relaxed text-muted-foreground">
        <span className="font-semibold text-foreground">Analysis · {artifact.symbol}</span>{" "}
        · {artifact.icbIndustry} · phiên {artifact.tradingDay} ·{" "}
        <span className="uppercase tracking-wide">
          {VERDICT_LABEL[artifact.verdict]}
        </span>
        {artifact.windowHealth.adjustment === "mixed" && (
          <span className="text-rose-600"> · cửa sổ mixed</span>
        )}
      </div>
      {onExpand && <ExpandButton onClick={onExpand} />}
    </div>
  )
}

function PriceZoneSentence({ artifact }: { artifact: AnalysisArtifact }) {
  const z = artifact.priceZone
  const span = z.bandCeilingVnd - z.bandFloorVnd
  const pct = (v: number) => ((v - z.bandFloorVnd) / span) * 100
  return (
    <p className="text-[13.5px] leading-relaxed text-foreground/90">
      Đóng cửa <strong className="font-mono font-semibold">{formatVnd(z.closeVnd)}</strong>,
      nằm trong vùng dao động thường ngày{" "}
      <strong className="font-mono font-semibold">
        {formatVnd(z.ordinaryLowVnd)}–{formatVnd(z.ordinaryHighVnd)}
      </strong>{" "}
      ({z.basis}); biên phiên ±{z.bandPct}% là {formatVnd(z.bandFloorVnd)}–
      {formatVnd(z.bandCeilingVnd)}.
      <span className="relative mt-2 block h-1.5 w-full max-w-sm rounded-full bg-secondary">
        <span
          className="absolute top-0 h-1.5 rounded-full bg-primary/35"
          style={{
            left: `${pct(z.ordinaryLowVnd)}%`,
            width: `${pct(z.ordinaryHighVnd) - pct(z.ordinaryLowVnd)}%`,
          }}
        />
        <span
          className="absolute -top-1 h-3.5 w-[2px] -translate-x-1/2 rounded-full bg-foreground"
          style={{ left: `${pct(z.closeVnd)}%` }}
        />
      </span>
    </p>
  )
}

function AxisParagraph({
  section,
  cited,
}: {
  section: AxisSection
  cited: Set<string>
}) {
  return (
    <p className="text-[13.5px] leading-relaxed text-foreground/90">
      <span
        className={cn(
          "mr-1.5 align-middle text-[10px] font-semibold uppercase tracking-wider",
          section.emphasis === "lead" ? "text-foreground" : "text-muted-foreground"
        )}
      >
        {section.title}
        {section.emphasis === "lead" && (
          <span className="ml-1 rounded-sm bg-primary/20 px-1 py-px text-[9px]">dẫn</span>
        )}
      </span>
      {section.read}{" "}
      <span className="inline-flex flex-wrap items-center gap-1 align-middle">
        {section.figures.map((f) => (
          <Pill key={f.id} figure={f} decisive={cited.has(f.id)} />
        ))}
      </span>
    </p>
  )
}

function Pill({ figure: f, decisive }: { figure: Figure; decisive: boolean }) {
  const bad = f.health === "refused" || f.health === "insufficient_history"
  return (
    <span className="group relative inline-block">
      <span
        className={cn(
          "cursor-help whitespace-nowrap rounded border px-1.5 py-px font-mono text-[11px]",
          decisive
            ? "border-primary/40 bg-primary/10 font-semibold text-foreground"
            : "border-border bg-secondary/60 text-muted-foreground",
          bad && "border-dashed border-rose-300 bg-rose-50 text-rose-700"
        )}
      >
        {formatValue(f)}
        {f.value !== null && <span className="ml-0.5 font-normal">{f.unit}</span>}
      </span>
      <span className="pointer-events-none absolute bottom-full left-0 z-20 mb-1 hidden w-72 rounded-lg border border-border bg-popover p-2.5 text-left shadow-lg group-hover:block">
        <span className="block text-[11px] font-semibold">{f.label}</span>
        <code className="mt-0.5 block text-[10px] text-muted-foreground">{f.id}</code>
        <span className="mt-1.5 block text-[11px] leading-snug text-muted-foreground">
          {f.interpretation}
        </span>
        <span className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span className="rounded bg-secondary px-1 py-px font-medium">{f.kind}</span>
          <span className="rounded bg-secondary px-1 py-px font-medium">{f.source}</span>
          <span>as of {f.asOf}</span>
          {f.nullFpr !== undefined && <span>FPR {(f.nullFpr * 100).toFixed(1)}%</span>}
        </span>
        {f.ownHistory && (
          <span className="mt-1 block text-[10px] leading-snug text-muted-foreground">
            {f.ownHistory}
          </span>
        )}
        {f.reason && (
          <span className="mt-1 block text-[10px] leading-snug text-rose-700">
            {f.reason}
          </span>
        )}
      </span>
    </span>
  )
}

function Ledger({
  artifact,
  cited,
}: {
  artifact: AnalysisArtifact
  cited: Set<string>
}) {
  const rows = artifact.sections.flatMap((s) => s.figures.map((f) => ({ f, axis: s.title })))
  return (
    <aside className="border-l border-border bg-secondary/30 px-4 py-5">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Sổ chỉ số ({rows.length})
      </h3>
      <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
        {artifact.citedFieldIds.length} trong số này đã được nhận định trích dẫn — đánh dấu
        bằng vạch xanh.
      </p>
      <ul className="mt-3 space-y-1.5">
        {rows.map(({ f, axis }) => (
          <li
            key={f.id}
            className={cn(
              "rounded-md border-l-2 bg-card px-2 py-1.5",
              cited.has(f.id) ? "border-l-primary" : "border-l-transparent"
            )}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-[11px]">{f.label}</span>
              <span className="shrink-0 font-mono text-[11px] font-semibold">
                {formatValue(f)}
              </span>
            </div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[9px] uppercase tracking-wide text-muted-foreground">
              <span>{axis}</span>
              <span>·</span>
              <span>{f.kind}</span>
              {f.health !== "ok" && (
                <>
                  <span>·</span>
                  <span className="text-rose-600">{f.health}</span>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </aside>
  )
}
