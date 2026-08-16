"use client"

import Link from "next/link"

import type { AnalysisArtifact } from "@/lib/alpha-desk/analysis"
import { signalIssueSentence } from "@/lib/signal-issues"
import { cn } from "@/lib/utils"
import { AxisPanel } from "./axis-panel"
import { CHROME, NARRATION } from "./copy"
import { PriceZoneBand } from "./price-zone-band"
import { ArtifactRiskNotice } from "./risk-notice"
import { VerdictHeader } from "./verdict-header"

/**
 * The expanded treatment: the briefing.
 *
 * Verdict, thesis, price-zone band, then all four axes and their decisive
 * figures **in the same fixed order the inline tabs use** (`docs/specs/0002`
 * §5). Nothing is revealed here that the inline treatment hid — a `degraded` or
 * `refused` figure is visible in both, with its reason rendered, because
 * deferring honesty to the expanded view means most readers never meet it.
 *
 * What the expansion adds is *room*: the four axes side by side instead of one
 * at a time, and the registered field ids the inline treatment shows only a
 * count of. The ids are here because this is where a reader who wants to check
 * a number goes, and a count is a claim while an id is a thing they can look
 * up.
 */
export function Briefing({
  artifact,
  className,
}: {
  artifact: AnalysisArtifact
  className?: string
}) {
  return (
    <div className={cn("space-y-4", className)}>
      <VerdictHeader artifact={artifact} />

      <p className="text-sm leading-relaxed">
        {artifact.thesis ?? (
          <span className="text-muted-foreground">{NARRATION.noThesis}</span>
        )}
      </p>

      <PriceZoneBand zone={artifact.priceZone} />

      {/* Two columns where there is room, one where there is not — and in both
          cases the DOM order is the template's order, so the reading order is
          the same on every viewport.

          The lead axis takes the full width. That is the other half of what
          emphasis buys: which tab opens, and how much space an axis gets
          (`docs/specs/0002` §5). It is still the third row where the template
          puts it — space, never position. */}
      <div className="grid gap-4 sm:grid-cols-2">
        {artifact.axes.map((axis) => (
          <AxisPanel
            key={axis.axis}
            axis={axis}
            showFieldIds
            className={axis.emphasis === "lead" ? "sm:col-span-2" : undefined}
          />
        ))}
      </div>

      <WindowHealth artifact={artifact} />

      <CitedFields artifact={artifact} />

      <p className="text-[11px]">
        <Link
          href={`/analytics/deep-dive?symbol=${encodeURIComponent(artifact.symbol)}`}
          className="underline underline-offset-2"
        >
          {CHROME.deepDive}
        </Link>
      </p>

      <ArtifactRiskNotice />

      <Audit artifact={artifact} />
    </div>
  )
}

/**
 * The window the price zone was read over, and what was wrong with it.
 *
 * Part of the backend-owned envelope the artifact carries (`docs/specs/0002`
 * §5) and shown here rather than inline, because it is a fact about the whole
 * Analysis rather than about any one figure — every figure additionally carries
 * its own `sessionsUsed` and `windowDays`, since the fields in one envelope do
 * not share a window.
 *
 * Its degradations are Signal Issue codes and are translated like every other
 * one: a code on screen is the failure the vocabulary exists to prevent.
 */
function WindowHealth({ artifact }: { artifact: AnalysisArtifact }) {
  const health = artifact.windowHealth
  if (health === null) return null

  const sessions = numberOf(health.sessionsUsed)
  const window = numberOf(health.windowDays)
  const limitLocked = numberOf(health.limitLockDays)
  const degradations = Array.isArray(health.degradations)
    ? health.degradations.filter((code): code is string => typeof code === "string")
    : []

  if (sessions === null && window === null && degradations.length === 0) return null

  return (
    <div className="space-y-1">
      <p className="text-[11px] font-medium">{CHROME.windowHealth}</p>
      <p className="text-[11px] tabular-nums text-muted-foreground">
        {sessions ?? "—"} / {window ?? "—"} {CHROME.sessions}
        {limitLocked !== null && limitLocked > 0
          ? ` · ${limitLocked} ${CHROME.limitLocked}`
          : ""}
      </p>
      {degradations.length > 0 && (
        <ul className="space-y-0.5 text-[11px] text-muted-foreground">
          {degradations.map((code) => (
            <li key={code}>{signalIssueSentence(code)}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function numberOf(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

/**
 * The exact ids the verdict rests on.
 *
 * Filtered by the projection against the figures they name, so an id that
 * pointed at a refused figure is not listed here and is not counted inline
 * either — the two treatments cannot disagree about what the verdict stands on.
 */
function CitedFields({ artifact }: { artifact: AnalysisArtifact }) {
  if (artifact.citedFieldIds.length === 0) return null

  return (
    <div className="space-y-1">
      <p className="text-[11px] font-medium">{CHROME.fieldIds}</p>
      <ul className="flex flex-wrap gap-1" aria-label={CHROME.fieldIds}>
        {artifact.citedFieldIds.map((fieldId) => (
          <li
            key={fieldId}
            className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
          >
            {fieldId}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** How this Analysis came to exist, for the reader who wants to reconcile it. */
function Audit({ artifact }: { artifact: AnalysisArtifact }) {
  if (artifact.audit === null) return null

  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground">
      <dt>{CHROME.audit}</dt>
      <dd className="font-mono">
        {CHROME.template} v{artifact.schemaVersion} · {artifact.audit.fieldProfileVersion}{" "}
        · {artifact.audit.promptVersion} · {artifact.audit.model}
      </dd>
      <dt>fingerprint</dt>
      <dd className="truncate font-mono">{artifact.audit.inputFingerprint}</dd>
    </dl>
  )
}
