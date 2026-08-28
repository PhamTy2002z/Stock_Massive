"use client"

import { cn } from "@/lib/utils"

/**
 * The questions offered after an answer that got no reply of its own.
 *
 * Plain buttons rather than chips or a card grid: each one *is* the next
 * question, verbatim, so pressing it should feel like the reader typed it
 * themselves — `onPick` hands the composer that exact string rather than a
 * suggestion id the caller would have to look back up.
 *
 * `boxed` gives each row its own edges. Under an answer they are not wanted —
 * the answer above is what the questions belong to, and a border would cut them
 * off from it. Over the composer in an empty conversation there is no answer to
 * belong to, so without edges the row reads as body text nobody wrote.
 */
export function FollowUps({
  items,
  onPick,
  className,
  boxed = false,
}: {
  items: string[]
  onPick: (text: string) => void
  className?: string
  /** Draw each question as a bordered row rather than as a line of text. */
  boxed?: boolean
}) {
  if (items.length === 0) return null

  return (
    <div className={cn("grid", boxed ? "gap-1.5" : "gap-5", className)}>
      {items.map((item, index) => (
        <button
          key={`${index}-${item}`}
          type="button"
          onClick={() => onPick(item)}
          className={cn(
            "flex text-left text-row text-ink-3 transition-colors hover:text-foreground",
            boxed
              ? "items-start gap-2.5 rounded-card border border-border px-2.5 py-2 leading-[1.4] hover:bg-foreground/[0.045]"
              : "items-center gap-[0.85rem]",
          )}
        >
          <span
            className={cn("flex flex-none text-muted-foreground", boxed && "mt-0.5")}
            aria-hidden
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.6}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M5 5v9h11" />
              <polyline points="12 10 16 14 12 18" />
            </svg>
          </span>
          <span className="min-w-0">{item}</span>
        </button>
      ))}
    </div>
  )
}
