"use client"

import { useEffect, useState } from "react"
import { Check, Copy } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"

/** A quiet, local copy action for a table or code block inside an answer. */
export function MarkdownCopyButton({
  getText,
  label,
  copiedLabel,
  className,
}: {
  getText: () => string
  label: string
  copiedLabel: string
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
      await navigator.clipboard.writeText(getText())
      setCopied(true)
    } catch {
      toast.error("Trình duyệt không cho phép sao chép")
    }
  }

  const accessibleLabel = copied ? copiedLabel : label

  return (
    <button
      type="button"
      onClick={() => void copy()}
      title={accessibleLabel}
      aria-label={accessibleLabel}
      className={cn(
        "flex size-11 items-center justify-center rounded-lg text-ink-5",
        "transition-[background-color,color,transform] duration-150",
        "hover:bg-foreground/[0.06] hover:text-foreground active:translate-y-px",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        className,
      )}
    >
      {copied ? (
        <Check className="size-4 text-positive" strokeWidth={1.8} aria-hidden />
      ) : (
        <Copy className="size-4" strokeWidth={1.7} aria-hidden />
      )}
      <span className="sr-only" aria-live="polite">
        {copied ? copiedLabel : ""}
      </span>
    </button>
  )
}
