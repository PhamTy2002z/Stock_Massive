/**
 * Which chart, if any, the right-hand pane is currently about.
 *
 * A pure function over the Thread on screen and the Turn in flight, because
 * every rule here is a statement about ownership rather than about React:
 *
 * **A running Turn owns the pane.** The chart from the previous answer is still
 * in the transcript and still correct about the question it answered — but the
 * question on screen is now a different one, and a picture left standing under
 * a new question reads as an answer to it. So a live Turn shows work in
 * progress and the old chart is not offered.
 *
 * **The Thread is the scope.** The selector is handed the messages of the
 * Thread that is open, so switching Threads changes the answer by construction.
 * There is no cache of "the last chart seen" to leak across.
 *
 * **No chart is a state, not a failure.** A Signal Desk answer whose figures the
 * ledger would not admit settles with no visual key at all, and the pane says so
 * in one line while the ledger's gaps explain it properly in the chat column.
 */

import { isActive, type LiveTurn } from "./live-turn"
import { readVisual } from "./read-content"
import type { ThreadMessage, VisualPart } from "./types"

/**
 * The four things the pane can be showing.
 *
 * `empty` and `none` are two different emptinesses and they earn different
 * surfaces: nothing has been asked yet, versus this answer has no chart.
 */
export type DeskView =
  | { state: "empty" }
  | { state: "working" }
  | { state: "chart"; visual: VisualPart }
  | { state: "none" }

export function selectDeskView(
  messages: ThreadMessage[],
  live: LiveTurn,
  threadId: string | null,
): DeskView {
  // A Turn belonging to another Thread says nothing about this pane. The hook
  // clears on a switch, but the guard is cheap and the alternative is a
  // skeleton spinning over the wrong conversation.
  if (isActive(live) && (live.threadId === null || live.threadId === threadId)) {
    return { state: "working" }
  }
  const answers = messages.filter((message) => message.role === "assistant")
  const last = answers[answers.length - 1]
  if (last === undefined) return { state: "empty" }
  const visual = readVisual(last.content.visual)
  return visual === null ? { state: "none" } : { state: "chart", visual }
}
