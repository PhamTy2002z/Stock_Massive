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
      className={cn("space-y-3 rounded-lg border border-border/60 bg-card/40 p-3", className)}
    >
      {children}
    </article>
  )
}
