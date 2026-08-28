"use client"

import { useEffect, useRef, useState } from "react"

import type { DraftEntry } from "@/lib/alpha-desk/transcript"
import { SignalDeskCard } from "./signal-desk-card"
import { Markdown } from "./markdown"
import { MessageShell } from "./message-shell"
import { ReasoningTimeline } from "./reasoning-timeline"
import { TurnStatus } from "./turn-status"

/**
 * The Turn in flight, as far as it should be on screen.
 *
 * The same two things the canonical message shows, in the same order, so the
 * swap at the terminal event moves nothing on screen.
 *
 * What it carries is everything the user has already been shown, through every
 * ending. Cancel keeps it, a deadline keeps it, a failed route keeps it — the
 * status is a line underneath, never a replacement.
 *
 * **How much of the answer is on screen is not this component's decision.** The
 * pacer that grows it lives above the view (`use-answer-reveal`), because every
 * step of it has to be a commit of the transcript — that is what lets the pin
 * and the spacer hold a question still while an answer arrives — and because it
 * has to survive the reader switching views mid-answer. What arrives here is
 * already the prefix to draw, and `working` is the one thing about the Turn that
 * the prefix cannot say: whether the timeline still reads as running.
 *
 * There is no separate "waiting" line. Everything that says the Turn has not
 * stopped is in the timeline, which is on screen for the whole of the wait and
 * ends in a row that moves.
 */
export function DraftMessage({
  entry,
  onRetry,
  onOpenDeskView,
  className,
}: {
  entry: DraftEntry
  onRetry: () => void
  /**
   * Opens one of the pictures this Turn has already produced.
   *
   * On the draft as well as on the canonical answer, because the panel opens
   * itself when the desk view is announced and a reader who closes it would
   * otherwise have no way back to it until the answer lands.
   */
  onOpenDeskView?: (artifactId: string) => void
  className?: string
}) {
  const elapsedMs = useTickingElapsed(entry.elapsedMs, entry.working)

  return (
    <MessageShell className={className}>
      {/* The work, above the answer, because that is the order it happened in
          and because a list growing *under* the thing the reader is waiting for
          would push the answer down the page while they read it. */}
      <ReasoningTimeline
        thoughts={entry.thoughts}
        toolCalls={entry.toolCalls}
        elapsedMs={elapsedMs}
        running={entry.working}
      />

      {/* Rendered as the Markdown it is, mid-sentence and all: the prefix grows
          by whole words, so a closing marker can be one word behind the text it
          closes. A syntax character on screen for a moment is the price of prose
          that appears as it is written, and holding it back until it parsed
          cleanly would be the buffering this whole path exists to avoid. */}
      {entry.text !== "" && <Markdown text={entry.text} animate />}

      {onOpenDeskView !== undefined && (
        <SignalDeskCard deskViews={entry.deskViews} onOpen={onOpenDeskView} />
      )}

      <TurnStatus
        phase={entry.phase}
        terminalReason={entry.terminalReason}
        onRetry={onRetry}
      />
    </MessageShell>
  )
}

/**
 * How long the Turn has been running, ticking between the events that say so.
 *
 * The backend reports `elapsed_ms` on the snapshot and on the terminal event and
 * on nothing in between, so a line reading it straight would say `0s` for the
 * whole of a Turn and then jump to the real figure at the end. This counts from
 * the last figure it was given, which is also what makes a reattached Turn
 * honest: the number carries how long the *Turn* has run, not how long this tab
 * has been watching it.
 *
 * A second's resolution, because the line is written in seconds.
 */
function useTickingElapsed(baseMs: number, ticking: boolean): number {
  const anchor = useRef({ base: baseMs, at: Date.now() })
  const [ticked, setTicked] = useState(baseMs)

  useEffect(() => {
    anchor.current = { base: baseMs, at: Date.now() }
    setTicked((was) => Math.max(was, baseMs))
  }, [baseMs])

  useEffect(() => {
    if (!ticking) return
    const timer = window.setInterval(
      () => setTicked(anchor.current.base + (Date.now() - anchor.current.at)),
      1000,
    )
    return () => window.clearInterval(timer)
  }, [ticking])

  // Never backwards. The count stops where the work stopped and stays there
  // until the terminal event supplies the figure the backend measured, which is
  // the one the finished line keeps — a number that ticked past it by a fraction
  // of a second is not worth a digit changing under the reader.
  return Math.max(ticked, baseMs)
}
