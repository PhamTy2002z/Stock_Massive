"use client"

/**
 * PROTOTYPE — throwaway. Issue #21. Variant D — "Pinned verdict + tabbed axes".
 *
 * The answer this variant argues for: an artifact in a transcript must have a
 * *bounded* height, because the thread scrolls and there may be ten of these in
 * it. So the verdict and the price zone are pinned, and the four axes are tabs —
 * one visible at a time, fixed height regardless of how much each axis has.
 *
 * Per-industry emphasis is expressed as *which tab opens first* plus a marker on
 * it. The tab set and order never change. Expanding trades the tabs for a 2×2
 * grid of all four axes at once.
 */

import * as React from "react"
import { ArrowUpRight } from "lucide-react"
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

export const VARIANT_D_NAME = "Pinned verdict + tabs"

const VERDICT_TONE: Record<string, string> = {
  accumulate: "bg-primary text-primary-foreground",
  hold: "bg-secondary text-secondary-foreground",
  watch: "bg-amber-100 text-amber-900",
  reduce: "bg-rose-100 text-rose-900",
  avoid: "bg-rose-600 text-white",
}

export function VariantD({ artifact }: { artifact: AnalysisArtifact }) {
  const { expanded, setExpanded } = useExpanded()
  const sections = orderedSections(artifact)
  const lead = sections.find((s) => s.emphasis === "lead") ?? sections[0]
  const [active, setActive] = React.useState(lead.axis)

  // A new symbol brings a new lead axis; the open tab follows it.
  React.useEffect(() => setActive(lead.axis), [lead.axis])

  const current = sections.find((s) => s.axis === active) ?? lead
  const cited = new Set(artifact.citedFieldIds)

  return (
    <>
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <PinnedHead artifact={artifact} onExpand={() => setExpanded(true)} />

        <div className="flex items-stretch gap-0 border-b border-border bg-secondary/30 px-1">
          {sections.map((s) => (
            <button
              key={s.axis}
              type="button"
              onClick={() => setActive(s.axis)}
              className={cn(
                "relative flex-1 px-2 py-2 text-[11px] font-medium transition-colors",
                s.axis === active
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="inline-flex items-center gap-1">
                {s.emphasis === "lead" && (
                  <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                )}
                {s.title}
              </span>
              {s.axis === active && (
                <span className="absolute inset-x-1 -bottom-px h-0.5 bg-foreground" />
              )}
            </button>
          ))}
        </div>

        {/* Fixed height: the point of this variant. */}
        <div className="flex min-h-[13.5rem] flex-col px-4 py-3">
          <AxisBody section={current} cited={cited} />
        </div>

        <BottomBar artifact={artifact} />
      </div>

      {expanded && (
        <ExpandOverlay onClose={() => setExpanded(false)}>
          <div className="px-5 py-4">
            <PinnedHead artifact={artifact} />
            <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
              {artifact.thesis}
            </p>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {sections.map((s) => (
                <div
                  key={s.axis}
                  className={cn(
                    "rounded-lg border border-border p-3",
                    s.emphasis === "lead" && "border-primary/40 bg-primary/[0.03]"
                  )}
                >
                  <AxisBody section={s} cited={cited} />
                </div>
              ))}
            </div>
            <div className="mt-4">
              <BottomBar artifact={artifact} flat />
            </div>
          </div>
        </ExpandOverlay>
      )}
    </>
  )
}

function PinnedHead({
  artifact,
  onExpand,
}: {
  artifact: AnalysisArtifact
  onExpand?: () => void
}) {
  const z = artifact.priceZone
  const span = z.bandCeilingVnd - z.bandFloorVnd
  const pct = (v: number) => ((v - z.bandFloorVnd) / span) * 100

  return (
    <div className="border-b border-border px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold tracking-tight">{artifact.symbol}</span>
            <Badge
              className={cn(
                "rounded-full border-transparent",
                VERDICT_TONE[artifact.verdict]
              )}
            >
              {VERDICT_LABEL[artifact.verdict]}
            </Badge>
          </div>
          <p className="mt-1 text-[12px] font-medium leading-snug">{artifact.verdictLine}</p>
        </div>
        <div className="shrink-0 text-right">
          <div className="font-mono text-lg font-semibold leading-none">
            {formatVnd(z.closeVnd)}
          </div>
          <div className="mt-1 font-mono text-[10px] text-muted-foreground">
            {formatVnd(z.ordinaryLowVnd)}–{formatVnd(z.ordinaryHighVnd)}
          </div>
          {onExpand && (
            <div className="mt-1.5">
              <ExpandButton onClick={onExpand} />
            </div>
          )}
        </div>
      </div>

      <div className="relative mt-2.5 h-1.5 w-full rounded-full bg-secondary">
        <div
          className="absolute top-0 h-1.5 rounded-full bg-primary/35"
          style={{
            left: `${pct(z.ordinaryLowVnd)}%`,
            width: `${pct(z.ordinaryHighVnd) - pct(z.ordinaryLowVnd)}%`,
          }}
        />
        <div
          className="absolute -top-1 h-3.5 w-[2px] -translate-x-1/2 rounded-full bg-foreground"
          style={{ left: `${pct(z.closeVnd)}%` }}
        />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
        <span>
          {artifact.icbIndustry} · {artifact.exchange} · phiên {artifact.tradingDay}
        </span>
        <span
          className={cn(artifact.windowHealth.adjustment === "mixed" && "text-rose-600")}
        >
          {artifact.windowHealth.sessions} phiên · {artifact.windowHealth.adjustment}
        </span>
      </div>
    </div>
  )
}

function AxisBody({ section, cited }: { section: AxisSection; cited: Set<string> }) {
  return (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          {section.title}
        </span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {section.emphasis}
        </span>
      </div>
      <p className="mt-1 text-[13px] leading-snug">{section.read}</p>
      <p className="mt-1 text-[10.5px] italic leading-snug text-muted-foreground">
        {section.emphasisReason}
      </p>
      <div className="mt-2.5 grid flex-1 gap-1.5 sm:grid-cols-2">
        {section.figures.map((f) => (
          <Tile key={f.id} figure={f} decisive={cited.has(f.id)} />
        ))}
      </div>
    </>
  )
}

function Tile({ figure: f, decisive }: { figure: Figure; decisive: boolean }) {
  const bad = f.health === "refused" || f.health === "insufficient_history"
  return (
    <div
      className={cn(
        "rounded-md border px-2 py-1.5",
        decisive ? "border-primary/40 bg-primary/[0.05]" : "border-border",
        bad && "border-dashed bg-secondary/40"
      )}
      title={f.interpretation}
    >
      <div className="truncate text-[10px] text-muted-foreground">{f.label}</div>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span
          className={cn(
            "font-mono text-[13px] font-semibold",
            bad && "font-normal text-muted-foreground"
          )}
        >
          {formatValue(f)}
        </span>
        {f.value !== null && (
          <span className="text-[9px] text-muted-foreground">{f.unit}</span>
        )}
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[9px] text-muted-foreground">
        <span>{f.kind}</span>
        {f.source === "stored" && <span>· {f.asOf}</span>}
        {f.health === "degraded" && <span className="text-amber-700">· degraded</span>}
        {bad && <span className="text-rose-600">· {f.health}</span>}
      </div>
      {/* A refusal is the most load-bearing thing on the tile — it never hides
          in a tooltip. */}
      {f.reason && (
        <p
          className={cn(
            "mt-1 text-[9.5px] leading-snug",
            bad ? "text-rose-700" : "text-amber-700"
          )}
        >
          {f.reason}
        </p>
      )}
    </div>
  )
}

function BottomBar({ artifact, flat }: { artifact: AnalysisArtifact; flat?: boolean }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 px-4 py-2.5",
        flat ? "rounded-lg bg-secondary/40" : "bg-secondary/40"
      )}
    >
      <span
        className="text-[10px] text-muted-foreground"
        title={artifact.citedFieldIds.join("\n")}
      >
        {artifact.citedFieldIds.length} registered field được trích dẫn · claim{" "}
        <code className="text-[10px]">{artifact.claim}</code>
      </span>
      <a
        href={`/analytics/deep-dive?symbol=${artifact.symbol}`}
        className="inline-flex items-center gap-1 text-[11px] font-medium text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
      >
        Stock 360
        <ArrowUpRight className="h-3 w-3" />
      </a>
      <p className="w-full text-[9.5px] leading-relaxed text-muted-foreground">
        {artifact.disclaimer}
      </p>
    </div>
  )
}
