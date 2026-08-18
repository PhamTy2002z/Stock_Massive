/**
 * Every word the Analysis artifact says, and which language each is in.
 *
 * The split is a product rule, not a style: application chrome and registered
 * field labels are **English**, matching the rest of the app; model narration
 * and human-readable health reasons are **Vietnamese** (`docs/specs/0002` §5).
 * Held here so the rule is checkable by reading one file rather than by
 * auditing every component that renders a word.
 *
 * The health reasons themselves are not here — they are one Vietnamese sentence
 * per Signal Issue code in `@/lib/signal-issues`, which is the one place that
 * vocabulary is translated. Two tables would be two answers to "why is this
 * number missing".
 */

import type { Axis, Emphasis, Health } from "@/lib/alpha-desk/analysis"

/** The four axes as the reader sees them. Chrome, therefore English. */
export const AXIS_LABEL: Record<Axis, string> = {
  technical: "Technical",
  fundamental: "Fundamental",
  money_flow: "Money flow",
  news: "News",
}

/** What a section's derived health is called. Also chrome. */
export const HEALTH_LABEL: Record<Health, string> = {
  ok: "ok",
  degraded: "degraded",
  refused: "refused",
}

/**
 * How each health state is coloured, in one place.
 *
 * A figure's border, a figure's badge and a section's badge all say the same
 * thing about the same three values, and three cascades over one union is how a
 * degraded figure ends up amber in one spot and grey three lines below.
 *
 * Colour is never the only carrier: every one of these sits beside
 * `HEALTH_LABEL`, because a state a reader can only get from a hue is a state
 * some readers cannot get at all.
 */
export const HEALTH_TONE: Record<Health, { border: string; badge: string }> = {
  ok: {
    border: "border-l-emerald-500/50",
    badge: "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
  },
  degraded: {
    border: "border-l-amber-500/60",
    badge: "border-amber-500/40 text-amber-600 dark:text-amber-400",
  },
  refused: {
    border: "border-l-muted-foreground/40",
    badge: "border-border text-muted-foreground",
  },
}

/**
 * How much of the artifact an axis gets, expressed as its own word.
 *
 * Emphasis is visible as which tab opens and how much space an axis takes —
 * never as a reordering — so the label is a caption on that, not a ranking the
 * reader is invited to re-sort by.
 */
export const EMPHASIS_LABEL: Record<Emphasis, string> = {
  lead: "lead",
  support: "support",
  context: "context",
}

/** Chrome: control labels, column headings, and the one deep-link caption. */
export const CHROME = {
  expand: "Expand",
  collapse: "Collapse",
  close: "Close",
  briefing: "Briefing",
  priceZone: "Ordinary daily range",
  citations: "Citations",
  fieldIds: "Registered field ids",
  windowHealth: "Window health",
  limitLocked: "limit-locked",
  audit: "Audit",
  asOf: "as of",
  sessions: "sessions",
  window: "window",
  noFigures: "No figures in this section",
  deepDive: "Open in deep dive",
  template: "template",
} as const

/**
 * The Vietnamese narration the artifact says on the system's behalf.
 *
 * Distinct from the model's own narration, which arrives in the payload. These
 * are the sentences a reader meets where the payload has nothing — an artifact
 * that fell back to silence there would look like a rendering bug rather than
 * like an Analysis with a hole in it.
 */
export const NARRATION = {
  loading: "Đang tải Analysis…",
  missing: "Không đọc được Analysis này.",
  zoneRefused: "Chưa dựng được vùng giá thường ngày cho phiên này.",
  noThesis: "Bản Analysis này không kèm luận điểm.",
  noRead: "Không có phần đọc cho trục này.",
  /** Said beside a refused figure, so the blank is read as evidence. */
  refusedIsEvidence: "Không dùng được để chống đỡ nhận định",
} as const

/**
 * How the price zone reads in one line.
 *
 * A number, never a target: the sentence says how far the symbol ordinarily
 * travels in a session and carries no view on where it will travel
 * (`docs/specs/0002` §5).
 */
export function priceZoneSentence(halfWidthPct: number): string {
  const width = halfWidthPct.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return `Biên độ thường ngày của mã này là ±${width}% quanh giá tham chiếu.`
}
