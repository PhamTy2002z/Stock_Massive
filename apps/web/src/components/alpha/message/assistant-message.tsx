"use client"

import { useState } from "react"

import { terminalSentence } from "@/lib/alpha-desk/copy"
import type { AssistantView } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { CanvasCard } from "./canvas-card"
import { FlagAction } from "./flag-action"
import { FollowUps } from "./follow-ups"
import { Markdown } from "./markdown"
import { MessageActions } from "./message-actions"
import { MessageShell } from "./message-shell"
import { ReasoningTimeline } from "./reasoning-timeline"
import { SourcePill } from "./source-pill"

/**
 * One canonical assistant message: the work, the answer, and what to do next.
 *
 * This is what replaces the draft at a terminal event, and the first two things
 * are the same two things in the same order — which is the point. The swap
 * happens while the reader is reading, so anything the canonical message added
 * or moved above the answer would make it jump under them. What the canonical
 * message adds, it adds *below*: the actions and the follow-ups, neither of
 * which can exist on a draft because both name a message that has been written.
 *
 * The controls are conditional on the *handlers* rather than on the message: a
 * surface with nowhere to send a flag renders no control at all, instead of one
 * that swallows the press. It is also why this component takes a message id — a
 * flag names a message, and the draft above it does not have one yet.
 *
 * **Thumbs down opens the four reasons rather than replacing them.** The
 * vocabulary — wrong figure, overreach, wrongly refused, other — is what makes a
 * flag readable when the answers are reviewed, and a bare down-vote would throw
 * that away for one icon's worth of tidiness. Thumbs up is its own mark and
 * carries no reason, because there is nothing to categorise about an answer
 * that worked.
 */
export function AssistantMessage({
  view,
  messageId,
  flaggedReason = null,
  flagFailed = false,
  helpful = false,
  onFlag,
  onUnflag,
  onHelpful,
  onCopy,
  onShare,
  onRegenerate,
  onFollowUp,
  onOpenSources,
  onOpenCanvas,
  className,
}: {
  view: AssistantView
  messageId?: number
  flaggedReason?: FlagReason | null
  flagFailed?: boolean
  /** Whether this answer already carries the reader's positive mark. */
  helpful?: boolean
  onFlag?: (messageId: number, reason: FlagReason) => void
  onUnflag?: (messageId: number) => void
  onHelpful?: (messageId: number, helpful: boolean) => void
  onCopy?: (text: string) => void
  onShare?: (messageId: number) => void
  onRegenerate?: (messageId: number) => void
  onFollowUp?: (text: string) => void
  /** Opens the panel listing every page behind this answer. */
  onOpenSources?: (messageId: number) => void
  /** Opens the panel drawing one of the pictures this answer produced. */
  onOpenCanvas?: (artifactId: string) => void
  className?: string
}) {
  // Whether the reason menu is open. Held here rather than inside the action
  // row because the row is a row of buttons and this is a conversation between
  // two of them: pressing thumbs-down opens the menu, and choosing a reason —
  // which happens in `FlagAction` — closes it.
  const [reasonsOpen, setReasonsOpen] = useState(false)

  const flaggable =
    messageId !== undefined && onFlag !== undefined && onUnflag !== undefined
  const actionable = messageId !== undefined

  return (
    <MessageShell className={className}>
      <ReasoningTimeline
        thoughts={view.thoughts}
        toolCalls={view.toolCalls}
        elapsedMs={view.elapsedMs}
        running={false}
      />

      <Markdown text={view.text} />

      {/* A Turn that stopped early left text that looks exactly like a finished
          answer's, so the fragment says so rather than leaving the reader to
          notice. Never in place of the text: what arrived is still worth
          reading. */}
      {!view.completed && (
        <p role="status" className="text-meta text-muted-foreground">
          {terminalSentence(null)}
        </p>
      )}

      {/* Above the actions and above the sources, because a picture the answer
          was written about is closer to the answer than the pages behind it. */}
      {onOpenCanvas !== undefined && (
        <CanvasCard canvases={view.canvases} onOpen={onOpenCanvas} />
      )}

      {/* Above the actions, because it is about the answer rather than about
          what to do with it. */}
      {actionable && onOpenSources !== undefined && (
        <SourcePill
          toolCalls={view.toolCalls}
          onOpen={() => onOpenSources(messageId)}
        />
      )}

      {actionable && (
        <MessageActions
          liked={helpful}
          disliked={flaggedReason !== null}
          onLike={
            onHelpful === undefined
              ? undefined
              : () => {
                  setReasonsOpen(false)
                  onHelpful(messageId, !helpful)
                }
          }
          // Down-vote does not record anything by itself. It asks which of the
          // four things went wrong, and the answer to that is the flag.
          onDislike={() =>
            flaggedReason !== null
              ? onUnflag?.(messageId)
              : setReasonsOpen((open) => !open)
          }
          onCopy={() => onCopy?.(view.text)}
          onShare={() => onShare?.(messageId)}
          onRegenerate={() => onRegenerate?.(messageId)}
        />
      )}

      {flaggable && (reasonsOpen || flaggedReason !== null || flagFailed) && (
        <FlagAction
          messageId={messageId}
          reason={flaggedReason}
          failed={flagFailed}
          onFlag={(id, reason) => {
            setReasonsOpen(false)
            onFlag(id, reason)
          }}
          onUnflag={(id) => {
            setReasonsOpen(false)
            onUnflag(id)
          }}
        />
      )}

      {/* Only under the newest answer, which is the caller's judgement to make:
          a suggestion under an answer three questions back would send the
          reader somewhere the conversation has already left. */}
      {view.followUps.length > 0 && onFollowUp !== undefined && (
        <FollowUps items={view.followUps} onPick={onFollowUp} />
      )}
    </MessageShell>
  )
}
