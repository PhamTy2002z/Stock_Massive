"use client"

import { cn } from "@/lib/utils"

/**
 * The box an assistant answer sits in, draft or canonical.
 *
 * One component because the swap between them has to be invisible: at a
 * terminal event the draft is replaced by the message the backend committed,
 * and if the two carried their own padding and border the answer would twitch
 * at the exact moment the user is reading it. Sharing the shell makes that
 * impossible rather than merely unlikely.
 *
 * The shell is no longer a card. The reference sets an answer as prose on the
 * page — the question above it is the thing in a bubble, and framing the reply
 * as well makes the conversation read as two columns of boxes instead of as
 * someone answering. What is left is the measure and the leading: 1.62, which
 * is what the reference sets its body copy at.
 */
export function MessageShell({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <article
      aria-label="Assistant message"
      className={cn("space-y-4 leading-[1.62] text-ink-2", className)}
    >
      {children}
    </article>
  )
}
