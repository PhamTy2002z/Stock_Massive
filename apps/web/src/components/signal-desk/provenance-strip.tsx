"use client"

/**
 * When the numbers were frozen, how wide the window was, and how whole it is.
 *
 * Three facts on **one line**, and they are shown together because none of them
 * answers the reader's question alone. A date without the session count does not
 * say whether the picture is of a habit or a fortnight; a session count without
 * the health does not say whether those sessions were whole.
 *
 * **The age is said out loud.** `asOf` is frozen when the Study ran, so a Thread
 * re-opened next week renders the same picture — correctly — and a reader
 * glancing at it would read it as today. So the strip does not merely print a
 * date, it says how old it is. Anything under a day is left as the date alone:
 * "hôm nay" beside a full timestamp is noise.
 *
 * **Two things it deliberately does not say.**
 *
 * `source` is gone. It named a data provider and a layer of this system, which
 * tells a reader looking at a liquidity profile nothing they can act on and
 * puts an internal word at the head of the most-read line on the desk.
 *
 * `reason` is one sentence for a reader, and the Study contract now checks it
 * for length and for the system's own words before it is frozen. Artifacts
 * frozen before that check may still carry refusal codes or internal English
 * prose; `readableReason` maps the first and drops the second, so the strip
 * never prints a log line whatever era the row is from.
 *
 * And it never wraps. A reason of any length is one truncated line, because the
 * strip is a caption and a caption that grows into a paragraph pushes the chart
 * it captions off the fold.
 */

import { useState } from "react"

import type { Provenance } from "@/lib/alpha-desk/types"
import { SIGNAL_ISSUE_SENTENCES, type SignalIssueCode } from "@/lib/signal-issues"
import { cn } from "@/lib/utils"

/** What each health value means to a reader, in the words the lane already uses. */
const HEALTH: Record<Provenance["health"], { label: string; tone: string }> = {
  normal: { label: "đầy đủ", tone: "text-muted-foreground" },
  degraded: { label: "thiếu một phần", tone: "text-caution" },
  unavailable: { label: "không đọc được", tone: "text-negative" },
}

const METHOD_LABEL = "Cách tính"

export function ProvenanceStrip({ provenance }: { provenance: Provenance }) {
  const health = HEALTH[provenance.health] ?? HEALTH.normal
  const day = readableDay(provenance.asOf)
  const age = ageInDays(provenance.asOf)
  const reason = readableReason(provenance.reason)
  const notes = provenance.methodNotes ?? []

  return (
    <div className="mt-1">
      <p className="flex items-center gap-x-2 overflow-hidden whitespace-nowrap text-meta text-muted-foreground">
        <span className="flex-none">
          dữ liệu {day}
          {age !== null && age >= 1 && ` (${age} ngày trước)`}
        </span>
        <span className="flex-none" aria-hidden>
          ·
        </span>
        <span className="flex-none">{provenance.sessionsUsed} phiên</span>
        <span className="flex-none" aria-hidden>
          ·
        </span>
        <span className={cn("flex-none", health.tone)}>{health.label}</span>
        {reason !== null && (
          <>
            <span className="flex-none" aria-hidden>
              ·
            </span>
            {/* The only part allowed to be long, and so the only one that gives
                way: one line, cut with an ellipsis, never a second row. */}
            <span className="min-w-0 truncate">{reason}</span>
          </>
        )}
      </p>
      {notes.length > 0 && <MethodNotes notes={notes} />}
    </div>
  )
}

/**
 * How the numbers were arrived at, folded away until asked for.
 *
 * A disclosure rather than a line on the strip: method is what a reader checks
 * once they have decided the picture matters, and every chart on the desk would
 * otherwise carry a paragraph above it that almost nobody reads.
 */
function MethodNotes({ notes }: { notes: string[] }) {
  const [open, setOpen] = useState(false)

  return (
    <details className="mt-1" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer text-meta text-muted-foreground hover:text-ink-2">
        {METHOD_LABEL}
      </summary>
      {open && (
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-meta text-muted-foreground">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </details>
  )
}

/**
 * The reason as a reader may see it, or `null` where it may not be shown.
 *
 * Three shapes arrive here, from three eras of artifact. A Study frozen today
 * writes one Vietnamese sentence, checked at the far end against the same
 * vocabulary rule this strip keeps — that one is shown as it is. An older run
 * wrote refusal codes joined by `;` — those go through the Vietnamese mapping
 * every coded reason in this product uses. And an older run still may have
 * written internal English prose — *"store holds 21 of 30 sessions"* — which is
 * dropped whole. All or nothing per reason: a string half translated reads as a
 * product that half-finished, where the health word alone reads as one that
 * declined to leak a log line.
 */
export function readableReason(reason: string | null): string | null {
  if (reason === null) return null
  const trimmed = reason.trim()
  if (trimmed === "") return null
  const parts = trimmed
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part !== "")
  const sentences: string[] = []
  for (const part of parts) {
    const sentence = SIGNAL_ISSUE_SENTENCES[part as SignalIssueCode]
    if (sentence === undefined) {
      sentences.length = 0
      break
    }
    sentences.push(sentence)
  }
  if (sentences.length === parts.length && parts.length > 0) return sentences.join(" · ")
  return isReaderSentence(trimmed) ? trimmed : null
}

/** Words that are this system talking about itself; mirrors the Study contract. */
const SHOP_WORDS =
  /\b(store|frame|artifact|widget|column|dataframe|endpoint|payload|schema|registry|tool|row)\b/i

/** A snake_case token is a code, and a code is never a sentence for a reader. */
const SNAKE_CASE = /\b[a-z0-9]+(?:_[a-z0-9]+)+\b/

function isReaderSentence(text: string): boolean {
  return !SNAKE_CASE.test(text) && !SHOP_WORDS.test(text)
}

/** The as-of as a Vietnamese date, or the raw string if it is not one. */
function readableDay(asOf: string): string {
  const moment = new Date(asOf)
  if (Number.isNaN(moment.getTime())) return asOf
  return moment.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

/** How many whole days ago the numbers were frozen, or null if unreadable. */
function ageInDays(asOf: string): number | null {
  const moment = new Date(asOf)
  if (Number.isNaN(moment.getTime())) return null
  return Math.floor((Date.now() - moment.getTime()) / 86_400_000)
}
