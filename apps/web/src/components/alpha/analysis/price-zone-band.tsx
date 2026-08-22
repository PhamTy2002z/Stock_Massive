"use client"

import { formatFieldValue } from "@/lib/units"
import type { FigureView } from "@/lib/alpha-desk/analysis"
import { priceZoneExtent } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import { CHROME, NARRATION, priceZoneSentence } from "./copy"

/**
 * The only inline graphic the artifact draws.
 *
 * Every other picture deep-links to `/analytics/deep-dive`, because one number
 * lives in one place (`docs/specs/0002` §5) and a second chart here would be a
 * second answer to a question Stock 360 already answers. This one earns its
 * place because the zone *is* a range and a range read as two numbers in a
 * sentence is a range the reader has to draw themselves.
 *
 * **It is a range, not a target.** The band is centred on the anchor close and
 * carries no arrow, no projection and no shading that could be read as a
 * direction — the field is a realized σ computed in code, and it reads that
 * way.
 *
 * A refused zone draws nothing at all and says why. A band shaped from a
 * half-present figure would be a picture standing for nothing.
 */
export function PriceZoneBand({
  zone,
  className,
}: {
  zone: FigureView | null
  className?: string
}) {
  const band = priceZoneExtent(zone)

  if (band === null) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        {zone?.reason ?? NARRATION.zoneRefused}
      </p>
    )
  }

  const lower = formatFieldValue(band.lower, "vnd")
  const upper = formatFieldValue(band.upper, "vnd")
  const anchor = formatFieldValue(band.anchor, "vnd")
  const halfWidth = halfWidthOnScale(band.halfWidthPct)

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
        <span className="font-medium">{CHROME.priceZone}</span>
        <span className="tabular-nums text-muted-foreground">
          {lower} – {upper}
        </span>
      </div>

      {/* Drawn to scale, on a scale that is named. A fixed rectangle would make
          a ±2% symbol and a ±15% one look identical, which is a picture
          asserting something untrue about the only number it shows. The two
          prices and the anchor are written out above, so the drawing adds
          proportion and nothing else — which is what lets it be `aria-hidden`
          rather than a chart a screen reader has to narrate. */}
      <svg
        viewBox="0 0 100 8"
        preserveAspectRatio="none"
        aria-hidden
        className="h-2 w-full"
      >
        <rect x="0" y="3" width="100" height="2" rx="1" className="fill-muted" />
        <rect
          x={50 - halfWidth}
          y="2"
          width={halfWidth * 2}
          height="4"
          rx="2"
          className="fill-primary/30 stroke-primary/60"
          strokeWidth="0.5"
        />
        <line
          x1="50"
          y1="0"
          x2="50"
          y2="8"
          className="stroke-foreground/70"
          strokeWidth="1"
        />
      </svg>

      <p className="text-micro text-muted-foreground">
        {priceZoneSentence(band.halfWidthPct)} {scaleNote(band.halfWidthPct)}{" "}
        {CHROME.asOf} <span className="tabular-nums">{zone?.asOf ?? "—"}</span> ·{" "}
        {anchor}
      </p>
    </div>
  )
}

/**
 * The scale the band is drawn against, as a half-width in percent.
 *
 * Ten, because the widest daily band any Vietnamese board permits is HOSE's ±7%
 * and UPCOM's ±15% applies to a session rather than to an ordinary one: a scale
 * of ten leaves an ordinary symbol visibly narrow and a volatile one visibly
 * wide, without the loudest name in the Universe pinning every other band to a
 * sliver.
 */
const SCALE_PCT = 10

/** Half the band's width in viewBox units, clamped so it stays a shape. */
function halfWidthOnScale(halfWidthPct: number): number {
  const share = Math.min(Math.abs(halfWidthPct) / SCALE_PCT, 1)
  return Math.max(share * 50, 1.5)
}

/**
 * The scale, said out loud where the band is clipped.
 *
 * A band already at the edge of the drawing is a band the picture cannot show
 * honestly, so it says so rather than letting the shape stand for a number it
 * no longer represents.
 */
function scaleNote(halfWidthPct: number): string {
  return Math.abs(halfWidthPct) > SCALE_PCT
    ? `Hình vẽ giới hạn ở ±${SCALE_PCT}%.`
    : ""
}
