"use client"

import { useEffect, useRef } from "react"

import { AnalysisCard } from "@/components/alpha/analysis"
import type { TranscriptEntry } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { AssistantMessage } from "./assistant-message"
import { DraftMessage } from "./draft-message"
import { FirstRun } from "./first-run"

/**
 * The conversation, in its own scroll container.
 *
 * **The transcript scrolls, not the page.** The shell is pinned to one viewport
 * so the dock and the composer stay where the user left them; if this element
 * did not own its overflow, a long answer would push the composer off the
 * bottom of the screen and the whole frame would travel with the content.
 *
 * Following the newest content is conditional on the user already being at the
 * bottom. Someone who scrolled up to re-read an earlier answer is reading it,
 * and yanking them back down every time a block arrives is the one behaviour
 * that makes a streaming transcript unusable.
 */

// How close to the bottom still counts as "following". Generous enough to
// survive a block landing between the scroll event and this measurement.
const FOLLOW_THRESHOLD_PX = 120

export function Transcript({
  entries,
  opening,
  onRetry,
  onFlag,
  onUnflag,
  flagFailedFor = null,
  className,
}: {
  entries: TranscriptEntry[]
  /**
   * What an empty conversation opens on. Defaults to the first-run copy alone;
   * the container passes the version with the greeting and the session glance,
   * both of which need hooks this component must not own.
   */
  opening?: React.ReactNode
  onRetry: () => void
  /**
   * Flagging one canonical assistant message, and clearing it again.
   *
   * Optional as a pair: a transcript with nowhere to send a flag renders no
   * control rather than one that does nothing when pressed.
   */
  onFlag?: (messageId: number, reason: FlagReason) => void
  onUnflag?: (messageId: number) => void
  /** The message whose last flag write was rejected, if any. */
  flagFailedFor?: number | null
  className?: string
}) {
  const container = useRef<HTMLDivElement>(null)
  const following = useRef(true)

  const lastEntry = entries.at(-1)
  const blockCount = lastEntry?.kind === "draft" ? lastEntry.blocks.length : 0

  useEffect(() => {
    const element = container.current
    if (!element || !following.current) return
    // Assigned rather than animated. A smooth scroll per block turns a fast
    // answer into a moving target, and it is motion the user did not ask for —
    // which is also why this needs no reduced-motion branch.
    element.scrollTop = element.scrollHeight
  }, [entries.length, blockCount])

  function onScroll() {
    const element = container.current
    if (!element) return
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight
    following.current = distance <= FOLLOW_THRESHOLD_PX
  }

  return (
    <div
      ref={container}
      onScroll={onScroll}
      className={cn("scrollbar-thin overflow-y-auto overscroll-contain", className)}
    >
      {entries.length === 0 ? (
        (opening ?? <FirstRun />)
      ) : (
        <div className="mx-auto w-full max-w-[760px] space-y-7 px-4 py-5">
          {entries.map((entry) => {
            if (entry.kind === "user") {
              return (
                <div key={entry.key} className="flex justify-end">
                  {/* The question is the one thing in a bubble, and it is the
                      bubble surface rather than the muted one: on a near-black
                      ground `bg-muted` sits a single percent off the page and
                      the bubble stops reading as a bubble. */}
                  <p
                    className={cn(
                      "max-w-[82%] animate-vg-message-in whitespace-pre-wrap rounded-2xl bg-surface-bubble px-[1.05em] py-[0.7em] text-[0.95rem] leading-[1.5] text-foreground",
                      entry.pending && "opacity-70",
                    )}
                  >
                    {entry.text}
                  </p>
                </div>
              )
            }

            if (entry.kind === "assistant") {
              return (
                <AssistantMessage
                  key={entry.key}
                  view={entry.view}
                  messageId={entry.messageId}
                  flaggedReason={entry.flaggedReason}
                  flagFailed={entry.messageId === flagFailedFor}
                  onFlag={onFlag}
                  onUnflag={onUnflag}
                />
              )
            }

            if (entry.kind === "analysis") {
              return (
                <AnalysisCard
                  key={entry.key}
                  symbol={entry.symbol}
                  tradingDay={entry.tradingDay}
                />
              )
            }

            return <DraftMessage key={entry.key} entry={entry} onRetry={onRetry} />
          })}
        </div>
      )}
    </div>
  )
}
