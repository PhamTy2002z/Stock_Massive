"use client"

import type { AssistantView } from "@/lib/alpha-desk/transcript"
import { ContentBlockView } from "./content-block"
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
 */
export function AssistantMessage({
  view,
  className,
}: {
  view: AssistantView
  className?: string
}) {
  return (
    <MessageShell className={className}>
      {view.blocks.map((block, index) => (
        <ContentBlockView key={`block-${index}`} block={block} />
      ))}

      <RiskNoticePanel notice={view.riskNotice} />

      <SourcesAndMethods rows={view.sourcesAndMethods} />
    </MessageShell>
  )
}
