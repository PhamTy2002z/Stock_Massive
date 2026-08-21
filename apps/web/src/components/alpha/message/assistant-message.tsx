"use client"

import type { AssistantView } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { AnswerActions } from "./answer-actions"
import { ContentBlockView } from "./content-block"
import { FlagAction } from "./flag-action"
import { MessageShell } from "./message-shell"
import { SearchProgress } from "./search-progress"
import { sourcesOf } from "./source-list"
import { Suggestions } from "./suggestions"

/**
 * One canonical assistant message.
 *
 * This is what replaces the draft at a terminal event, and it is the fuller
 * thing: the same blocks, plus the trail the Turn left, the sources the backend
 * attached in the terminal transaction, and the follow-ups it generated.
 *
 * The order on screen is the order of a finished answer rather than of a Turn:
 * the trail folds up **above** the prose, because how the answer was reached is
 * context for reading it and never the thing itself, and the actions sit under
 * it where the next question is about to be typed.
 *
 * The Risk Notice the backend attaches (`view.riskNotice`) is deliberately not
 * rendered. It is still carried on the message and still assembled server-side;
 * the product decision is that it does not belong on this surface, so the
 * renderer drops it rather than the contract losing it.
 *
 * The flag action is conditional, and it is conditional on the *handlers*
 * rather than on the message: a surface with nowhere to send a flag renders no
 * control at all, instead of one that swallows the press. It is also why this
 * component takes a message id — a flag names a message, and the draft above it
 * does not have one yet.
 */
export function AssistantMessage({
  view,
  messageId,
  flaggedReason = null,
  flagFailed = false,
  onFlag,
  onUnflag,
  onRetry,
  onAsk,
  showSuggestions = false,
  className,
}: {
  view: AssistantView
  messageId?: number
  flaggedReason?: FlagReason | null
  flagFailed?: boolean
  onFlag?: (messageId: number, reason: FlagReason) => void
  onUnflag?: (messageId: number) => void
  /** Ask the question above this answer again. */
  onRetry?: () => void
  /** Put a follow-up in the composer, unsent. */
  onAsk?: (question: string) => void
  /** Only the newest answer offers follow-ups; see `Suggestions`. */
  showSuggestions?: boolean
  className?: string
}) {
  const sources = sourcesOf(view.searchProgress)

  return (
    <MessageShell className={className}>
      <SearchProgress
        steps={view.searchProgress}
        activity={null}
        // The trail closes with what the Turn actually ended as, rather than
        // leaving the reader to infer it from the absence of a spinner. A Turn
        // that hit its deadline says so: its blocks look identical to a whole
        // answer's, and this row is the difference.
        ending={
          view.searchProgress.length === 0 ? null : view.completed ? "done" : "stopped"
        }
      />

      {view.blocks.map((block, index) => (
        <ContentBlockView key={`block-${index}`} block={block} />
      ))}

      <AnswerActions
        text={view.blocks.map((block) => block.text).join("\n\n")}
        sources={sources}
        onRetry={onRetry}
      />

      {messageId !== undefined && onFlag !== undefined && onUnflag !== undefined && (
        <FlagAction
          messageId={messageId}
          reason={flaggedReason}
          failed={flagFailed}
          onFlag={onFlag}
          onUnflag={onUnflag}
        />
      )}

      {showSuggestions && onAsk !== undefined && (
        <Suggestions questions={view.suggestions} onAsk={onAsk} className="pt-2" />
      )}
    </MessageShell>
  )
}
