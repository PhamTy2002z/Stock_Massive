"use client"

import { useEffect, useState } from "react"
import { Check, Copy, RotateCcw } from "lucide-react"

import { PROGRESS_COPY } from "@/lib/alpha-desk/copy"
import type { ProgressSource } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { SourceDrawer } from "./source-drawer"
import { SourceCluster } from "./source-list"

/**
 * The quiet row under an answer: copy it, ask again, or see what it stood on.
 *
 * Three controls and no labels, because this row sits between one answer and
 * the next question and anything louder competes with both. It is mounted
 * always rather than revealed on hover: a row that appears under the pointer is
 * a row a keyboard cannot reach.
 *
 * The sources control is a **count with faces on it** — the icons of the hosts
 * behind the answer, then how many there were. That is the provenance worth a
 * line under an answer: whether it rests on somebody recognisable. Pressing it
 * opens the source drawer beside the conversation rather than unfolding a list
 * into it — see `SourceDrawer` for why. Figure-level provenance stays where it
 * is actionable, one press behind the chip on the claim itself
 * (`citation-chips`), rather than repeated as a list under the answer.
 */
export function AnswerActions({
  text,
  sources,
  onRetry,
  className,
}: {
  /** The whole answer, for the clipboard. */
  text: string
  /** The public pages behind it, deduplicated by the trail. */
  sources: ProgressSource[]
  /** Ask the same question again, or absent where there is nothing to re-ask. */
  onRetry?: () => void
  className?: string
}) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(timer)
  }, [copied])

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      // A browser that refuses the clipboard — no permission, an insecure
      // origin — is not worth an error over text the reader can still select.
    }
  }

  const total = sources.length
  if (!text && total === 0 && onRetry === undefined) return null

  return (
    <div className={cn("flex items-center gap-1", className)}>
      {text && (
        <IconAction label={copied ? "Đã sao chép" : "Sao chép"} onClick={() => void copy()}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        </IconAction>
      )}

      {onRetry && (
        <IconAction label="Hỏi lại" onClick={onRetry}>
          <RotateCcw className="size-4" />
        </IconAction>
      )}

      {total > 0 && (
        <SourceDrawer sources={sources}>
          <button
            type="button"
            className="ml-1 flex items-center gap-2 rounded-lg px-1.5 py-1 text-meta text-ink-5 transition-colors hover:text-ink-2"
          >
            <SourceCluster sources={sources} />
            {PROGRESS_COPY.sourcesLabel(total)}
          </button>
        </SourceDrawer>
      )}
    </div>
  )
}

function IconAction({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="grid size-7 place-items-center rounded-lg text-ink-5 transition-colors hover:bg-surface-raised hover:text-ink-2"
    >
      {children}
    </button>
  )
}
