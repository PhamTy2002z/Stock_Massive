"use client"

import { cn } from "@/lib/utils"

/**
 * The questions offered after an answer that got no reply of its own.
 *
 * Plain buttons rather than chips or a card grid: each one *is* the next
 * question, verbatim, so pressing it should feel like the reader typed it
 * themselves — `onPick` hands the composer that exact string rather than a
 * suggestion id the caller would have to look back up.
 */
export function FollowUps({
  items,
  onPick,
  className,
}: {
  items: string[]
  onPick: (text: string) => void
  className?: string
}) {
  if (items.length === 0) return null

  return (
    <div className={cn("grid gap-5", className)}>
      {items.map((item, index) => (
        <button
          key={`${index}-${item}`}
          type="button"
          onClick={() => onPick(item)}
          className="flex items-center gap-[0.85rem] text-left text-row text-ink-3 transition-colors hover:text-foreground"
        >
          <span className="flex flex-none text-muted-foreground" aria-hidden>
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
          {item}
        </button>
      ))}
    </div>
  )
}
