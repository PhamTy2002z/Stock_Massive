"use client"

import { useMemo } from "react"

// Through the barrel, which is the boundary the registry states: a component
// reached around it is a component reached without its `(name, version)` check.
import { MessageWidgets, widgetResolverFor } from "@/components/alpha/widgets"
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
 * **Widgets need a message id, and that is why only this component draws them.**
 * A Widget is resolved through the message that stores its descriptor, so the id
 * is not a convenience here — it is the whole retrieval path, and it is what
 * makes a reopened Thread show the same historical slice (ADR-0012). The draft
 * above has no id yet, which is why a `widget.ready` mid-Turn puts nothing on
 * screen until the canonical message replaces the draft a moment later. The
 * alternative would be resolving a descriptor through some route that does not
 * name a message, and that route is exactly the one the design does not have.
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
  // Bound to the message rather than rebuilt per render. The slot reads its
  // resolver through a ref precisely so a new function identity cannot restart
  // a fetch (`widget-slot`), and memoising here keeps that defence from being
  // the only thing standing between a streaming transcript and a refetch loop.
  const resolveWidget = useMemo(
    () => (messageId === undefined ? null : widgetResolverFor(messageId)),
    [messageId],
  )

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

      {/* Under the prose and above the actions: a Widget is evidence for the
          answer just given, where the action row is where the reader turns to
          the next question. */}
      {messageId !== undefined && resolveWidget !== null && (
        <MessageWidgets
          messageId={messageId}
          widgets={view.widgets}
          refusals={view.widgetRefusals}
          resolve={resolveWidget}
        />
      )}

      {/* One row, not two. Copy, ask-again, sources and flag are all the same
          kind of thing — what the reader does *with* the answer — and stacking
          the flag underneath read as a second, more serious bar. It wraps
          rather than overflows, because the flag carries its recorded reason
          as text once one is chosen. */}
      <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
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
      </div>

      {showSuggestions && onAsk !== undefined && (
        <Suggestions questions={view.suggestions} onAsk={onAsk} className="pt-2" />
      )}
    </MessageShell>
  )
}
