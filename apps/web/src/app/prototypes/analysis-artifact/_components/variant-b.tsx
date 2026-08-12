"use client"

/**
 * PROTOTYPE — throwaway. Issue #21. Variant B — "Data sheet".
 *
 * The answer this variant argues for: the artifact is a figure ledger, and the
 * prose is a footnote. One table, fixed columns, four axis groups in fixed
 * order. Per-industry emphasis shows up as *which rows are marked decisive* and
 * which industry-specific fields occupy each group's slots — never as layout.
 *
 * Deliberately anti-dashboard: no hero paragraph, no graphic. The price zone is
 * a table row like everything else, so one number lives in one column.
 */

import * as React from "react"
import { ArrowUpRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { ExpandButton, ExpandOverlay, useExpanded } from "./expand"
import {
  type AnalysisArtifact,
  type Figure,
  VERDICT_LABEL,
  formatValue,
  formatVnd,
  orderedSections,
} from "./fixtures"

export const VARIANT_B_NAME = "Data sheet"

export function VariantB({ artifact }: { artifact: AnalysisArtifact }) {
  const { expanded, setExpanded } = useExpanded()
  const [showAll, setShowAll] = React.useState(false)

  const cited = new Set(artifact.citedFieldIds)
  const sections = orderedSections(artifact)
  const total = sections.reduce((n, s) => n + s.figures.length, 0)

  const body = (full: boolean) => {
    const all = full || showAll
    return (
      <>
        <TopStrip
          artifact={artifact}
          onExpand={full ? undefined : () => setExpanded(true)}
        />

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-border bg-secondary/50 text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-1.5 font-medium">Figure</th>
                <th className="px-3 py-1.5 text-right font-medium">Value</th>
                <th className="px-3 py-1.5 font-medium">Unit</th>
                <th className="px-3 py-1.5 font-medium">Kind</th>
                <th className="px-3 py-1.5 font-medium">Vs own history</th>
                <th className="px-3 py-1.5 font-medium">As of</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <td className="border-l-2 border-l-primary px-3 py-2">
                  <div className="text-[12px] font-medium">Vùng dao động thường ngày</div>
                  <code className="text-[10px] text-muted-foreground">
                    {artifact.priceZone.fieldId}
                  </code>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-[12px] font-semibold">
                  {formatVnd(artifact.priceZone.ordinaryLowVnd)} –{" "}
                  {formatVnd(artifact.priceZone.ordinaryHighVnd)}
                </td>
                <td className="px-3 py-2 text-[11px] text-muted-foreground">VND</td>
                <td className="px-3 py-2 text-[11px]">
                  <KindChip kind="estimator" />
                </td>
                <td className="px-3 py-2 text-[11px] text-muted-foreground">
                  đóng cửa {formatVnd(artifact.priceZone.closeVnd)} · biên ±
                  {artifact.priceZone.bandPct}%
                </td>
                <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground">
                  {artifact.priceZone.asOf}
                </td>
              </tr>

              {sections.map((s) => {
                const rows = all ? s.figures : s.figures.filter((f) => cited.has(f.id))
                return (
                  <React.Fragment key={s.axis}>
                    <tr className="border-b border-border bg-secondary/30">
                      <td colSpan={6} className="px-3 py-1.5">
                        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                          <span className="text-[11px] font-semibold uppercase tracking-wider">
                            {s.title}
                          </span>
                          <EmphasisTag emphasis={s.emphasis} />
                          <span className="text-[11px] text-muted-foreground">{s.read}</span>
                        </div>
                      </td>
                    </tr>
                    {rows.length === 0 && (
                      <tr className="border-b border-border">
                        <td
                          colSpan={6}
                          className="px-3 py-2 text-[11px] italic text-muted-foreground"
                        >
                          không có chỉ số nào của trục này được dùng cho nhận định
                        </td>
                      </tr>
                    )}
                    {rows.map((f) => (
                      <FigureRow key={f.id} figure={f} decisive={cited.has(f.id)} />
                    ))}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </div>

        {!full && (
          <div className="border-b border-border px-3 py-2">
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="text-[11px] font-medium text-muted-foreground underline decoration-border underline-offset-2 hover:text-foreground"
            >
              {all
                ? `Chỉ hiện ${artifact.citedFieldIds.length} chỉ số quyết định`
                : `Hiện toàn bộ ${total} chỉ số`}
            </button>
          </div>
        )}

        {artifact.news.length > 0 && (
          <div className="border-b border-border px-3 py-2.5">
            <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Tin đã dùng
            </div>
            <ul className="space-y-1">
              {artifact.news.map((n) => (
                <li key={n.title} className="text-[11px] leading-snug">
                  <span className="font-mono text-muted-foreground">{n.publishedAt}</span>{" "}
                  <span>{n.title}</span>{" "}
                  <span className="text-muted-foreground">· {n.source}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="space-y-2 bg-secondary/40 px-3 py-2.5">
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Model note
            </span>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              {artifact.thesis}
            </p>
          </div>
          <a
            href={`/analytics/deep-dive?symbol=${artifact.symbol}`}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
          >
            Stock 360 · {artifact.symbol}
            <ArrowUpRight className="h-3 w-3" />
          </a>
          <p className="text-[10px] leading-relaxed text-muted-foreground">
            {artifact.disclaimer}
          </p>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        {body(false)}
      </div>
      {expanded && (
        <ExpandOverlay onClose={() => setExpanded(false)}>{body(true)}</ExpandOverlay>
      )}
    </>
  )
}

function TopStrip({
  artifact,
  onExpand,
}: {
  artifact: AnalysisArtifact
  onExpand?: () => void
}) {
  const cells: Array<[string, React.ReactNode]> = [
    [
      "Verdict",
      <span key="v" className="text-sm font-bold uppercase tracking-tight">
        {VERDICT_LABEL[artifact.verdict]}
      </span>,
    ],
    [
      "Claim",
      <span key="c" className="font-mono text-[12px]">
        {artifact.claim}
      </span>,
    ],
    [
      "Window",
      <span
        key="w"
        className={cn(
          "font-mono text-[12px]",
          artifact.windowHealth.adjustment === "mixed" && "text-rose-600"
        )}
      >
        {artifact.windowHealth.sessions}d / {artifact.windowHealth.adjustment} /{" "}
        {artifact.windowHealth.limitDaysInWindow} limit
      </span>,
    ],
    [
      "Cited fields",
      <span key="f" className="font-mono text-[12px]">
        {artifact.citedFieldIds.length}
      </span>,
    ],
  ]

  return (
    <div className="border-b border-border">
      <div className="flex items-center justify-between gap-3 px-3 pt-2.5">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="font-mono text-base font-bold tracking-tight">
            {artifact.symbol}
          </span>
          <span className="truncate text-[11px] text-muted-foreground">
            {artifact.icbIndustry} · {artifact.exchange} · phiên {artifact.tradingDay}
          </span>
        </div>
        {onExpand && <ExpandButton onClick={onExpand} />}
      </div>
      <div className="mt-2 grid grid-cols-2 divide-x divide-border border-t border-border sm:grid-cols-4">
        {cells.map(([label, node]) => (
          <div key={label} className="px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {label}
            </div>
            <div className="mt-0.5">{node}</div>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-3 py-2">
        <p className="text-[12px] font-medium leading-snug">{artifact.verdictLine}</p>
      </div>
    </div>
  )
}

function EmphasisTag({ emphasis }: { emphasis: "lead" | "support" | "context" }) {
  const tone =
    emphasis === "lead"
      ? "bg-primary/20 text-foreground"
      : emphasis === "support"
        ? "bg-secondary text-muted-foreground"
        : "bg-transparent text-muted-foreground"
  return (
    <span
      className={cn(
        "rounded-sm px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide",
        tone
      )}
    >
      {emphasis}
    </span>
  )
}

function KindChip({ kind }: { kind: string }) {
  return (
    <span className="rounded bg-secondary px-1 py-px font-mono text-[10px] text-muted-foreground">
      {kind}
    </span>
  )
}

function FigureRow({ figure: f, decisive }: { figure: Figure; decisive: boolean }) {
  const bad = f.health === "refused" || f.health === "insufficient_history"
  return (
    <tr className={cn("border-b border-border", decisive && "bg-primary/[0.04]")}>
      <td
        className={cn(
          "px-3 py-2",
          decisive ? "border-l-2 border-l-primary" : "border-l-2 border-l-transparent"
        )}
      >
        <div className={cn("text-[12px]", decisive && "font-medium")}>{f.label}</div>
        <code className="text-[10px] text-muted-foreground">{f.id}</code>
        {f.reason && (
          <p className={cn("mt-0.5 text-[10px] leading-snug", bad ? "text-rose-700" : "text-amber-700")}>
            {f.reason}
          </p>
        )}
      </td>
      <td
        className={cn(
          "whitespace-nowrap px-3 py-2 text-right font-mono text-[12px]",
          bad ? "text-muted-foreground" : "font-semibold"
        )}
      >
        {formatValue(f)}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-[11px] text-muted-foreground">
        {f.unit}
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-col gap-0.5">
          <KindChip kind={f.kind} />
          {f.nullFpr !== undefined && (
            <span className="font-mono text-[9px] text-muted-foreground">
              FPR {(f.nullFpr * 100).toFixed(1)}%
            </span>
          )}
          {f.source === "stored" && (
            <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
              stored
            </span>
          )}
        </div>
      </td>
      <td className="px-3 py-2 text-[11px] leading-snug text-muted-foreground">
        {f.ownHistory ?? "—"}
      </td>
      <td className="whitespace-nowrap px-3 py-2 font-mono text-[10px] text-muted-foreground">
        {f.asOf}
      </td>
    </tr>
  )
}
