"use client"

/**
 * The figures that lead a board, in boxes, already looked up.
 *
 * **Nothing here formats a number.** `value.text` was produced by
 * `studies/format.py` at the moment the board was frozen, so a board re-opened
 * next year renders the string it was written with rather than one this build
 * derives from a rule it has since changed. Every other reader in this directory
 * formats, and this one deliberately does not.
 *
 * **Colour is a claim the engine made.** A box is inked in the page's own
 * foreground unless the board said what that figure *is* — the winner of a
 * comparison, a number that fell — so a coloured box on this strip always means
 * something was claimed, and the label beside it says the same thing in words.
 *
 * **The delta is a second cell, never a subtraction.** A strip that computed
 * "up 12%" from two figures would be the browser doing arithmetic on market
 * numbers, which is the one thing this whole track is built to prevent. What
 * arrives is a second reference the server resolved; the arrow is read off the
 * two raw values and says nothing the numbers do not.
 */

import { ArrowDown, ArrowUp } from "lucide-react"

import type { Kpi } from "@/lib/alpha-desk/types"

import { gridColumn } from "./layout"
import { cellColorFor } from "./widgets/chart-theme"

export function KpiStrip({ kpis, width }: { kpis: Kpi[]; width: number }) {
  if (kpis.length === 0) return null

  return (
    <dl
      className="grid grid-cols-12 gap-2"
      aria-label="Các con số dẫn dắt"
    >
      {kpis.map((kpi, index) => (
        <div
          key={`${kpi.label}-${index}`}
          style={{ gridColumn: gridColumn(kpi.span, width) }}
          className="min-w-0 rounded-[13px] border border-hairline bg-surface-sunken px-[15px] py-3.5"
        >
          <dt
            className="truncate text-[0.68rem] font-semibold uppercase leading-tight tracking-[0.09em] text-muted-foreground"
            title={kpi.label}
          >
            {kpi.label}
          </dt>
          <dd className="mt-2 flex min-w-0 items-baseline gap-1.5">
            <span
              className={`truncate font-mono text-[1.42rem] font-semibold leading-none tabular-nums tracking-[-0.02em] ${
                cellColorFor(kpi.role) === null ? "text-foreground" : ""
              }`}
              style={
                cellColorFor(kpi.role) === null
                  ? undefined
                  : { color: cellColorFor(kpi.role) as string }
              }
            >
              {kpi.value.text}
            </span>
            {kpi.delta !== null && <Delta from={kpi.delta} to={kpi.value} />}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/**
 * The second cell, and an arrow only where both raw values are numbers.
 *
 * No arrow otherwise, rather than a guess: a delta between two strings is a
 * comparison nobody made, and an arrow drawn from nothing is the surface making
 * a claim on the engine's behalf.
 */
function Delta({ from, to }: { from: Kpi["delta"]; to: Kpi["value"] }) {
  if (from === null) return null
  const before = typeof from.raw === "number" ? from.raw : null
  const after = typeof to.raw === "number" ? to.raw : null
  const rose = before !== null && after !== null ? after > before : null

  return (
    <span className="inline-flex shrink-0 items-center gap-0.5 font-mono text-meta tabular-nums text-muted-foreground">
      {rose === true && <ArrowUp aria-hidden className="h-3 w-3" />}
      {rose === false && <ArrowDown aria-hidden className="h-3 w-3" />}
      <span className="truncate">{from.text}</span>
    </span>
  )
}
