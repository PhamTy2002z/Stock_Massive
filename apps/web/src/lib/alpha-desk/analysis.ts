/**
 * What an Analysis payload becomes before anything draws it.
 *
 * The stored payload is JSONB written by a pipeline whose template has a
 * version column, so this module reads it defensively and answers with a shape
 * the renderer can trust: **four axes, in one order, with exactly one lead**.
 *
 * That is not a convenience. Section set and section order are invariant
 * (`docs/specs/0002` §5): the model chose `emphasis`, the lead tab and which
 * registered fields fill each axis's slots, and it chose none of the layout.
 * Deciding the order in JSX would put that rule where the only way to check it
 * is to render, and would let a payload whose `axes` arrived money-flow-first
 * quietly reorder the artifact. Here it cannot: the axes are built by walking
 * `AXIS_ORDER`, and what the payload carries is looked *up* rather than
 * iterated.
 *
 * Two more rules live here for the same reason:
 *
 * **A refused field can never support the verdict.** `citedFieldIds` is filtered
 * against the figures it names, so a payload citing a refused id shows a
 * citation count that matches what a reader can actually check.
 *
 * **A Signal Issue code never reaches the screen.** The payload's own `reason`
 * is the English sentence written for the model (`src/alpha/reasons.py`); the
 * reader's sentence is Vietnamese and comes from the one place that holds it.
 *
 * The keys here are camelCase because that is what the artifact contract puts
 * on the wire — unlike the REST shapes elsewhere in this app, which are snake.
 * The two spellings are the backend's and are not reconciled at this boundary.
 */

import type { AnalysisDetail } from "@/lib/alpha"
import { signalIssueSentence } from "@/lib/signal-issues"

/** The invariant section order. Never derived from a payload. */
export const AXIS_ORDER = ["technical", "fundamental", "money_flow", "news"] as const

export type Axis = (typeof AXIS_ORDER)[number]

/** Three values and a reason, never four states (`src/alpha/envelope.py`). */
export type Health = "ok" | "degraded" | "refused"

export type Emphasis = "lead" | "support" | "context"

export const PRICE_ZONE_FIELD_ID = "price_zone.ordinary_range_pct"

// -- what arrives ----------------------------------------------------------

export interface PayloadFigure {
  fieldId: string
  label: string
  value: number | null
  unit: string | null
  kind: string | null
  source: string | null
  interpretation: string
  health: Health
  reasonCode: string | null
  reason: string | null
  asOf: string | null
  sessionsUsed: number | null
  windowDays: number | null
  extras: Record<string, unknown>
}

export interface PayloadSection {
  axis: Axis
  health: Health
  figures: PayloadFigure[]
}

export interface PayloadAxisJudgment {
  axis: Axis
  emphasis: Emphasis
  emphasisReason: string
  read: string
}

export interface AnalysisPayload {
  audit: {
    schemaVersion: number
    fieldProfileVersion: string
    promptVersion: string
    model: string
    route: string
    generatedAt: string
    inputFingerprint: string
  }
  evidence: {
    schemaVersion: number
    fieldProfileVersion: string
    symbol: string
    companyName: string | null
    exchange: string | null
    industry: string
    tradingDay: string
    priceZone: PayloadFigure
    sections: PayloadSection[]
    windowHealth: Record<string, unknown>
  }
  judgment: {
    verdictLine: string
    thesis: string
    leadAxis: Axis
    axes: PayloadAxisJudgment[]
  }
  citedFieldIds: string[]
}

// -- what the renderer reads ----------------------------------------------

export interface FigureView {
  fieldId: string
  label: string
  value: number | null
  unit: string | null
  kind: string | null
  source: string | null
  interpretation: string | null
  health: Health
  /** Vietnamese, and present exactly when the health is not `ok`. */
  reason: string | null
  asOf: string | null
  sessionsUsed: number | null
  windowDays: number | null
  extras: Record<string, unknown>
  /** Whether the verdict actually rests on this figure. */
  cited: boolean
}

export interface AxisView {
  axis: Axis
  health: Health
  emphasis: Emphasis
  emphasisReason: string | null
  read: string | null
  figures: FigureView[]
}

export interface AnalysisArtifact {
  symbol: string
  tradingDay: string
  /** The extracted column, not a payload key: the rail reads it for ten symbols. */
  verdict: string
  verdictLine: string | null
  thesis: string | null
  /** The row's own template version — several are in circulation across days. */
  schemaVersion: number
  companyName: string | null
  exchange: string | null
  industry: string | null
  priceZone: FigureView | null
  axes: AxisView[]
  leadAxis: Axis
  /** What the inline treatment shows. The ids are the expanded view's. */
  citationCount: number
  citedFieldIds: string[]
  audit: AnalysisPayload["audit"] | null
  windowHealth: Record<string, unknown> | null
}

/** What the only inline graphic draws, or null when there is nothing to draw. */
export interface PriceZoneExtent {
  lower: number
  upper: number
  anchor: number
  halfWidthPct: number
}

export function buildArtifact(detail: AnalysisDetail): AnalysisArtifact {
  const payload = (detail.payload ?? {}) as Partial<AnalysisPayload>
  const evidence = isRecord(payload.evidence) ? payload.evidence : null
  const judgment = isRecord(payload.judgment) ? payload.judgment : null

  const sections = sectionsByAxis(evidence?.sections)

  // Read once and reused: the citation filter and the rendered figures must be
  // looking at the same figures, and building them twice is two answers to one
  // question.
  const priceZone = figureView(evidence?.priceZone)
  const figures = new Map<Axis, FigureView[]>(
    [...sections.entries()].map(([axis, section]) => [
      axis,
      section.figures
        .map((figure) => figureView(figure))
        .filter((figure): figure is FigureView => figure !== null),
    ]),
  )

  // Cited ids are filtered against the figures they name before anything reads
  // the count, so an id pointing at a refused figure — or at no figure at all —
  // cannot inflate what the artifact claims to rest on.
  //
  // The two conditions are `EvidenceFigure.citable`'s, verbatim: health is not
  // refused *and* a value is present (`src/alpha/envelope.py`). A figure with no
  // number is not evidence whatever its health says, and dropping the second
  // half here would let the artifact count a citation the backend's own
  // validator would have rejected.
  const usable = new Set(
    [priceZone, ...[...figures.values()].flat()]
      .filter((figure): figure is FigureView => figure !== null)
      .filter((figure) => figure.health !== "refused" && figure.value !== null)
      .map((figure) => figure.fieldId),
  )
  const cited = list(payload.citedFieldIds)
    .filter((id): id is string => typeof id === "string")
    .filter((id) => usable.has(id))
  const citedSet = new Set(cited)

  const judgments = judgmentsByAxis(judgment?.axes)
  const lead = leadAxis(judgment?.leadAxis, judgments)

  return {
    symbol: detail.symbol,
    tradingDay: detail.trading_day,
    verdict: detail.verdict,
    verdictLine: text(judgment?.verdictLine),
    thesis: text(judgment?.thesis),
    schemaVersion: detail.schema_version,
    companyName: text(evidence?.companyName),
    exchange: text(evidence?.exchange),
    industry: text(evidence?.industry),
    priceZone: withCitations(priceZone, citedSet),
    axes: AXIS_ORDER.map((axis) =>
      axisView(
        axis,
        sections.get(axis)?.health,
        figures.get(axis) ?? [],
        judgments.get(axis),
        axis === lead,
        citedSet,
      ),
    ),
    leadAxis: lead,
    citationCount: cited.length,
    citedFieldIds: cited,
    audit: isRecord(payload.audit) ? (payload.audit as AnalysisPayload["audit"]) : null,
    windowHealth: isRecord(evidence?.windowHealth)
      ? (evidence.windowHealth as Record<string, unknown>)
      : null,
  }
}

/**
 * The two prices the band is drawn between, or null.
 *
 * Null wherever the zone was refused or its prices are not in the payload: the
 * band is the only inline graphic the artifact draws, and drawing one from a
 * half-present figure would put a shape on screen that stands for nothing.
 */
export function priceZoneExtent(zone: FigureView | null): PriceZoneExtent | null {
  if (zone === null || zone.health === "refused" || zone.value === null) return null

  const lower = number(zone.extras.lower_price)
  const upper = number(zone.extras.upper_price)
  const anchor = number(zone.extras.anchor_close)
  if (lower === null || upper === null || anchor === null) return null
  if (!(lower < upper)) return null

  return { lower, upper, anchor, halfWidthPct: zone.value }
}

// -- the projection --------------------------------------------------------

function sectionsByAxis(sections: unknown): Map<Axis, PayloadSection> {
  const byAxis = new Map<Axis, PayloadSection>()
  for (const section of list(sections)) {
    if (!isRecord(section)) continue
    const axis = asAxis(section.axis)
    // A first writer wins, so a payload carrying one axis twice cannot have its
    // figures decided by array order.
    if (axis === null || byAxis.has(axis)) continue
    byAxis.set(axis, {
      axis,
      health: asHealth(section.health) ?? "refused",
      figures: list(section.figures).filter(isRecord) as unknown as PayloadFigure[],
    })
  }
  return byAxis
}

function judgmentsByAxis(axes: unknown): Map<Axis, PayloadAxisJudgment> {
  const byAxis = new Map<Axis, PayloadAxisJudgment>()
  for (const entry of list(axes)) {
    if (!isRecord(entry)) continue
    const axis = asAxis(entry.axis)
    if (axis === null || byAxis.has(axis)) continue
    byAxis.set(axis, {
      axis,
      emphasis: asEmphasis(entry.emphasis) ?? "context",
      emphasisReason: text(entry.emphasisReason) ?? "",
      read: text(entry.read) ?? "",
    })
  }
  return byAxis
}

/**
 * Which axis opens first, and the guarantee that exactly one does.
 *
 * The model may name a lead and mark one axis `lead`, and the two have to
 * agree; where they do not, or where a payload marks three, the first in
 * `AXIS_ORDER` wins and every other lead is demoted by `axisView`. A payload
 * with no lead at all still opens on one — a set of tabs where none is selected
 * is a broken artifact, not an honest one.
 */
function leadAxis(named: unknown, judgments: Map<Axis, PayloadAxisJudgment>): Axis {
  const declared = asAxis(named)
  if (declared !== null && judgments.get(declared)?.emphasis === "lead") return declared

  const marked = AXIS_ORDER.find((axis) => judgments.get(axis)?.emphasis === "lead")
  if (marked !== undefined) return marked

  return declared ?? AXIS_ORDER[0]
}

function axisView(
  axis: Axis,
  health: Health | undefined,
  figures: FigureView[],
  judgment: PayloadAxisJudgment | undefined,
  isLead: boolean,
  cited: Set<string>,
): AxisView {
  const emphasis = judgment?.emphasis ?? "context"
  return {
    axis,
    // An axis the payload never carried is refused rather than absent: the
    // template's membership is fixed, so the honest reading of a missing
    // section is that nothing in it could be used.
    health: health ?? "refused",
    emphasis: isLead ? "lead" : emphasis === "lead" ? "support" : emphasis,
    emphasisReason: text(judgment?.emphasisReason),
    read: text(judgment?.read),
    figures: figures.map((figure) => withCitations(figure, cited) as FigureView),
  }
}

/**
 * Whether the verdict rests on this figure, stamped once the list is known.
 *
 * Separate from building the figure because the citation list is filtered
 * *against* the figures: they have to exist before anything can say which of
 * them were cited.
 */
function withCitations(
  figure: FigureView | null,
  cited: Set<string>,
): FigureView | null {
  return figure === null ? null : { ...figure, cited: cited.has(figure.fieldId) }
}

function figureView(raw: unknown): FigureView | null {
  if (!isRecord(raw)) return null
  const fieldId = text(raw.fieldId)
  if (fieldId === null) return null

  const health = asHealth(raw.health) ?? "refused"
  const reasonCode = text(raw.reasonCode)

  return {
    fieldId,
    label: text(raw.label) ?? fieldId,
    value: number(raw.value),
    unit: text(raw.unit),
    kind: text(raw.kind),
    source: text(raw.source),
    interpretation: text(raw.interpretation),
    health,
    // The payload's own `reason` is English and was written for the model. A
    // reader's sentence is looked up from the code, which is also why a
    // `health` that is not `ok` with no code still reads as a sentence.
    reason:
      health === "ok"
        ? null
        : signalIssueSentence(reasonCode ?? "unnamed_signal_issue"),
    asOf: text(raw.asOf),
    sessionsUsed: number(raw.sessionsUsed),
    windowDays: number(raw.windowDays),
    extras: isRecord(raw.extras) ? (raw.extras as Record<string, unknown>) : {},
    // Stamped by `withCitations` once the filtered list exists.
    cited: false,
  }
}

// -- reading JSONB ---------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function asAxis(value: unknown): Axis | null {
  return AXIS_ORDER.includes(value as Axis) ? (value as Axis) : null
}

function asHealth(value: unknown): Health | null {
  return value === "ok" || value === "degraded" || value === "refused" ? value : null
}

function asEmphasis(value: unknown): Emphasis | null {
  return value === "lead" || value === "support" || value === "context" ? value : null
}
