"use client"

import type { AssistantView } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { ContentBlockView } from "./content-block"
import { FlagAction } from "./flag-action"
import { MessageShell } from "./message-shell"
import { RiskNoticePanel } from "./risk-notice"
import { SourcesAndMethods } from "./sources-and-methods"

/**
 * One canonical assistant message.
 *
 * This is what replaces the draft at a terminal event, and it is the fuller
 * thing: the same blocks, plus the Risk Notice and the sources the backend
 * attached in the terminal transaction.
 *
 * The Risk Notice is rendered unconditionally. There is no prop and no branch
 * that can omit it — a message reaching this component is a completed or
 * usefully incomplete answer, and both carry one (`docs/specs/0002` §11.6).
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
  onFlag,
  onUnflag,
  className,
}: {
  view: AssistantView
  messageId?: number
  flaggedReason?: FlagReason | null
  onFlag?: (messageId: number, reason: FlagReason) => void
  onUnflag?: (messageId: number) => void
  className?: string
}) {
  return (
    <MessageShell className={className}>
      {view.blocks.map((block, index) => (
        <ContentBlockView key={`block-${index}`} block={block} />
      ))}

      <RiskNoticePanel notice={view.riskNotice} />

      <SourcesAndMethods rows={view.sourcesAndMethods} />

      {messageId !== undefined && onFlag !== undefined && onUnflag !== undefined && (
        <FlagAction
          messageId={messageId}
          reason={flaggedReason}
          onFlag={onFlag}
          onUnflag={onUnflag}
        />
      )}
    </MessageShell>
  )
}
