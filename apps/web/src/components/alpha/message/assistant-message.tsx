"use client"

import type { AssistantView } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { ContentBlockView } from "./content-block"
import { FlagAction } from "./flag-action"
import { MessageShell } from "./message-shell"
import { SourcesAndMethods } from "./sources-and-methods"

/**
 * One canonical assistant message.
 *
 * This is what replaces the draft at a terminal event, and it is the fuller
 * thing: the same blocks, plus the sources the backend attached in the terminal
 * transaction.
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
      {view.blocks.map((block, index) => (
        <ContentBlockView key={`block-${index}`} block={block} />
      ))}

      <SourcesAndMethods rows={view.sourcesAndMethods} />

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
