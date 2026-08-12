"use client"

/**
 * PROTOTYPE — throwaway. Issue #21. Variant A — "Briefing card".
 *
 * The answer this variant argues for: an Analysis reads top-down like a
 * briefing. Verdict, then the thesis in prose, then the price zone as the one
 * graphic, then the four axes — where the *lead* axis is opened out and the
 * other three collapse to a single line each. Per-industry emphasis is
 * therefore visible as vertical space, and the DOM order of the axes never
 * changes.
 */

import * as React from "react"
import { ArrowUpRight, ChevronDown, ChevronRight } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { ExpandButton, ExpandOverlay, useExpanded } from "./expand"
import {
  type AnalysisArtifact,
  type AxisSection,
  type Figure,
  VERDICT_LABEL,
  formatValue,
  formatVnd,
  orderedSections,
} from "./fixtures"

export const VARIANT_A_NAME = "Briefing card"

const VERDICT_TONE: Record<string, string> = {
  accumulate: "bg-primary text-primary-foreground",
  hold: "bg-secondary text-secondary-foreground",
  watch: "bg-amber-100 text-amber-900",
  reduce: "bg-rose-100 text-rose-900",
  avoid: "bg-rose-600 text-white",
}

export function VariantA({ artifact }: { artifact: AnalysisArtifact }) {
  const { expanded, setExpanded } = useExpanded()
  const sections = orderedSections(artifact)

  const body = (full: boolean) => (
    <>
      <Header artifact={artifact} onExpand={full ? undefined : () => setExpanded(true)} />
      <div className="border-b border-border px-4 py-3.5">
        <p className="text-sm font-medium leading-snug text-foreground">
          {artifact.verdictLine}
        </p>
        <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
          {artifact.thesis}
        </p>
      </div>
      <PriceZoneStrip artifact={artifact} />
      <div className="divide-y divide-border">
        {sections.map((s) => (
          <AxisRow key={s.axis} section={s} forceOpen={full} />
        ))}
      </div>
      <Footer artifact={artifact} />
    </>
  )

  return (
    <>
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        {body(false)}
      </div>
      {expanded && (
        <ExpandOverlay onClose={() => setExpanded(false)}>
          <div className="mx-auto max-w-[64rem]">{body(true)}</div>
        </ExpandOverlay>
      )}
    </>
  )
}

function Header({
  artifact,
  onExpand,
}: {
  artifact: AnalysisArtifact
  onExpand?: () => void
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-base font-semibold tracking-tight">{artifact.symbol}</span>
          <span className="truncate text-xs text-muted-foreground">
            {artifact.companyName}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
          <span>{artifact.icbIndustry}</span>
          <span>·</span>
          <span>{artifact.exchange}</span>
          <span>·</span>
          <span>phiên {artifact.tradingDay}</span>
          <span>·</span>
          <span
            className={cn(
              artifact.windowHealth.adjustment === "mixed" && "text-rose-600"
            )}
          >
            {artifact.windowHealth.sessions} phiên · {artifact.windowHealth.adjustment}
          </span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge
          className={cn("rounded-full border-transparent", VERDICT_TONE[artifact.verdict])}
        >
          {VERDICT_LABEL[artifact.verdict]}
        </Badge>
        {onExpand && <ExpandButton onClick={onExpand} />}
      </div>
    </div>
  )
}

function PriceZoneStrip({ artifact }: { artifact: AnalysisArtifact }) {
  const z = artifact.priceZone
  const span = z.bandCeilingVnd - z.bandFloorVnd
  const pct = (v: number) => ((v - z.bandFloorVnd) / span) * 100

  return (
    <div className="border-b border-border px-4 py-3.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Vùng dao động thường ngày
        </span>
        <span className="font-mono text-[13px] font-medium">
          {formatVnd(z.ordinaryLowVnd)} – {formatVnd(z.ordinaryHighVnd)}
        </span>
      </div>

      <div className="relative mt-3 h-9">
        <div className="absolute inset-x-0 top-3 h-1.5 rounded-full bg-secondary" />
        <div
          className="absolute top-3 h-1.5 rounded-full bg-primary/35"
          style={{
            left: `${pct(z.ordinaryLowVnd)}%`,
            width: `${pct(z.ordinaryHighVnd) - pct(z.ordinaryLowVnd)}%`,
          }}
        />
        <div
          className="absolute top-1.5 h-5 w-[3px] -translate-x-1/2 rounded-full bg-foreground"
          style={{ left: `${pct(z.closeVnd)}%` }}
        />
        <div
          className="absolute top-[26px] -translate-x-1/2 whitespace-nowrap font-mono text-[11px] font-semibold"
          style={{ left: `${pct(z.closeVnd)}%` }}
        >
          {formatVnd(z.closeVnd)}
        </div>
        <span className="absolute left-0 top-[26px] font-mono text-[10px] text-muted-foreground">
          sàn {formatVnd(z.bandFloorVnd)}
        </span>
        <span className="absolute right-0 top-[26px] font-mono text-[10px] text-muted-foreground">
          trần {formatVnd(z.bandCeilingVnd)}
        </span>
      </div>

      <p className="mt-4 text-[11px] text-muted-foreground">
        {z.basis} · biên ±{z.bandPct}% · <code className="text-[10px]">{z.fieldId}</code>
      </p>
    </div>
  )
}

function AxisRow({ section, forceOpen }: { section: AxisSection; forceOpen: boolean }) {
  const isLead = section.emphasis === "lead"
  const [open, setOpen] = React.useState(isLead)
  const shown = forceOpen || open

  return (
    <div className={cn("px-4 py-3", isLead && "bg-primary/[0.03]")}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-2 text-left"
        disabled={forceOpen}
      >
        <span className="mt-0.5 shrink-0 text-muted-foreground">
          {shown ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[13px] font-semibold">{section.title}</span>
            {isLead && (
              <span className="rounded-sm bg-primary/20 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-foreground">
                trục dẫn
              </span>
            )}
            {section.emphasis === "context" && (
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                nền
              </span>
            )}
          </span>
          <span className="mt-0.5 block text-[13px] leading-snug text-muted-foreground">
            {section.read}
          </span>
        </span>
      </button>

      {shown && (
        <div className="mt-3 pl-[22px]">
          <p className="mb-3 border-l-2 border-border pl-2.5 text-[11px] italic leading-relaxed text-muted-foreground">
            {section.emphasisReason}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {section.figures.map((f) => (
              <FigureTile key={f.id} figure={f} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function FigureTile({ figure: f }: { figure: Figure }) {
  const bad = f.health === "refused" || f.health === "insufficient_history"
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card px-2.5 py-2",
        bad && "border-dashed bg-secondary/40"
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-[11px] text-muted-foreground">{f.label}</span>
        <span
          className={cn(
            "shrink-0 font-mono text-sm font-semibold",
            bad && "text-muted-foreground"
          )}
        >
          {formatValue(f)}
          {f.value !== null && (
            <span className="ml-1 text-[10px] font-normal text-muted-foreground">
              {f.unit}
            </span>
          )}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
        <span className="rounded bg-secondary px-1 py-px font-medium">{f.kind}</span>
        {f.source === "stored" && <span>as of {f.asOf}</span>}
        {f.nullFpr !== undefined && <span>FPR {(f.nullFpr * 100).toFixed(1)}%</span>}
        {f.health === "degraded" && <span className="text-amber-700">degraded</span>}
      </div>
      {f.ownHistory && (
        <p className="mt-1 text-[10px] leading-snug text-muted-foreground">{f.ownHistory}</p>
      )}
      {f.reason && (
        <p className="mt-1 text-[10px] leading-snug text-rose-700">{f.reason}</p>
      )}
    </div>
  )
}

function Footer({ artifact }: { artifact: AnalysisArtifact }) {
  return (
    <div className="space-y-2.5 bg-secondary/40 px-4 py-3">
      <div>
        <span className="text-[11px] font-medium text-muted-foreground">
          Nhận định dựa trên {artifact.citedFieldIds.length} registered field:
        </span>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {artifact.citedFieldIds.map((id) => (
            <code
              key={id}
              className="rounded bg-card px-1.5 py-0.5 text-[10px] text-muted-foreground"
            >
              {id}
            </code>
          ))}
        </div>
      </div>
      <a
        href={`/analytics/deep-dive?symbol=${artifact.symbol}`}
        className="inline-flex items-center gap-1 text-[12px] font-medium text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
      >
        Xem biểu đồ và báo cáo đầy đủ trong Stock 360
        <ArrowUpRight className="h-3 w-3" />
      </a>
      <p className="text-[10px] leading-relaxed text-muted-foreground">
        {artifact.disclaimer}
      </p>
    </div>
  )
}
