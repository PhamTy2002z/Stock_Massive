"use client"

import { useEffect, useState, type ReactNode } from "react"
import { Check, Link2 } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * The five controls under an answer: two verdicts, copy, share, regenerate.
 *
 * Icon-only and thirty pixels square, the same register `flag-action.tsx`
 * uses for the one dispute control this surface ships. A row labelled "Was
 * this helpful?" under every single answer competes with the answer for
 * attention on every one of them; icons that only gain a label on hover or to
 * a screen reader are meant to be glanced past on all but the reply a reader
 * actually stops on.
 *
 * `liked` / `disliked` are booleans the caller owns rather than local state —
 * whichever verdict (if any) is recorded lives with the message, so a
 * re-render after the caller's own write still shows the pressed state
 * instead of resetting it. Share is not in the design this was built from; it
 * is given the same 30px square and the same hover register as the four that
 * are, because a sixth kind of button here would read as a different control
 * rather than a fifth choice among equals.
 */
export function MessageActions({
  onCopy,
  onShare,
  onRegenerate,
  onLike,
  onDislike,
  liked,
  disliked,
  className,
}: {
  onCopy: () => void
  onShare: () => void
  onRegenerate: () => void
  /**
   * Records the reader's positive mark, or absent.
   *
   * Optional because the mark has to be *stored* somewhere to mean anything. A
   * surface with nowhere to put it renders no thumb at all, rather than one
   * that lights up and forgets — a control that looks like it recorded
   * something and did not is worse than a control that is not offered.
   */
  onLike?: () => void
  onDislike: () => void
  liked: boolean
  disliked: boolean
  className?: string
}) {
  const [justCopied, setJustCopied] = useState(false)

  // Mirrors `account-section.tsx`'s own copy feedback: the timer lives beside
  // the state it clears, so a second click while the label is still "Đã chép"
  // simply restarts the same effect instead of racing an older timer.
  useEffect(() => {
    if (!justCopied) return
    const timer = setTimeout(() => setJustCopied(false), 1600)
    return () => clearTimeout(timer)
  }, [justCopied])

  function handleCopy() {
    onCopy()
    setJustCopied(true)
  }

  return (
    <div className={cn("flex gap-1", className)}>
      {onLike !== undefined && (
        <ActionButton
          label="Hữu ích"
          onClick={onLike}
          pressed={liked}
          activeClassName="text-primary"
          hoverClassName="hover:text-primary"
        >
          <HelpfulIcon />
        </ActionButton>
      )}

      <ActionButton
        label="Chưa đúng"
        onClick={onDislike}
        pressed={disliked}
        activeClassName="text-destructive"
        hoverClassName="hover:text-destructive"
      >
        <IncorrectIcon />
      </ActionButton>

      <ActionButton label={justCopied ? "Đã chép" : "Sao chép"} onClick={handleCopy}>
        {justCopied ? <Check className="size-4" /> : <CopyIcon />}
      </ActionButton>

      <ActionButton label="Chia sẻ" onClick={onShare}>
        <Link2 className="size-4" strokeWidth={1.6} aria-hidden />
      </ActionButton>

      <ActionButton label="Tải lại" onClick={onRegenerate}>
        <ReloadIcon />
      </ActionButton>
    </div>
  )
}

function ActionButton({
  label,
  onClick,
  pressed,
  activeClassName,
  hoverClassName = "hover:text-foreground",
  children,
}: {
  label: string
  onClick: () => void
  /** Whether this verdict is the one already recorded. Undefined: no verdict concept. */
  pressed?: boolean
  activeClassName?: string
  hoverClassName?: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-pressed={activeClassName !== undefined ? Boolean(pressed) : undefined}
      className={cn(
        "flex h-[30px] w-[30px] items-center justify-center rounded-md text-muted-foreground transition-colors",
        "hover:bg-foreground/[0.06]",
        hoverClassName,
        pressed && activeClassName,
      )}
    >
      {children}
    </button>
  )
}

function HelpfulIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
    >
      <path d="M8 11.5 12 4l1.6.8a2 2 0 0 1 1 2.3L14 10h4.2a2 2 0 0 1 2 2.5l-1.4 5.5a2 2 0 0 1-2 1.5H8z" />
      <path d="M8 11.5V19H5.5a1 1 0 0 1-1-1v-5.5a1 1 0 0 1 1-1z" />
    </svg>
  )
}

function IncorrectIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
    >
      <path d="M16 12.5 12 20l-1.6-.8a2 2 0 0 1-1-2.3L10 14H5.8a2 2 0 0 1-2-2.5l1.4-5.5a2 2 0 0 1 2-1.5H16z" />
      <path d="M16 12.5V5h2.5a1 1 0 0 1 1 1v5.5a1 1 0 0 1-1 1z" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
    >
      <rect x="9" y="9" width="11" height="11" rx="2.5" />
      <path d="M15 6.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h.5" />
    </svg>
  )
}

function ReloadIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
    >
      <path d="M19.5 12a7.5 7.5 0 1 1-2.6-5.7" />
      <polyline points="19.8 4.5 19.8 8.5 15.8 8.5" />
    </svg>
  )
}
