"use client"

import { terminalSentence } from "@/lib/alpha-desk/copy"
import type { AssistantView } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { FlagAction } from "./flag-action"
import { Markdown } from "./markdown"
import { MessageShell } from "./message-shell"
import { ToolCallList } from "./tool-call-list"

/**
 * One canonical assistant message: the answer, and the calls behind it.
 *
 * This is what replaces the draft at a terminal event, and it is the same two
 * things in the same order — which is the point. The swap happens while the
 * reader is reading, so anything the canonical message added or moved would
 * make the answer jump under them.
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
  className,
}: {
  view: AssistantView
  messageId?: number
  flaggedReason?: FlagReason | null
  flagFailed?: boolean
  onFlag?: (messageId: number, reason: FlagReason) => void
  onUnflag?: (messageId: number) => void
  className?: string
}) {
  return (
    <MessageShell className={className}>
      <ToolCallList calls={view.toolCalls} />

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

      {messageId !== undefined && onFlag !== undefined && onUnflag !== undefined && (
        <FlagAction
          messageId={messageId}
          reason={flaggedReason}
          failed={flagFailed}
          onFlag={onFlag}
          onUnflag={onUnflag}
        />
      )}
    </MessageShell>
  )
}
