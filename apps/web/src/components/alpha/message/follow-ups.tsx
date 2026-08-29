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
 * Three shapes, because the row means something different in each place it
 * appears.
 *
 * *Plain* under an answer: the answer above is what the questions belong to, and
 * a border would cut them off from it.
 *
 * *`boxed`* over the composer in an ordinary empty conversation — there is no
 * answer to belong to, so without edges the row reads as body text nobody wrote.
 *
 * *`pill`* over the composer with the desk on. The desk's opening column is
 * narrow and already holds a hero line and a field, and three bordered cards
 * stacked in it read as a list to work through. A pill is one line, clipped
 * rather than wrapped, which is what keeps the offer subordinate to the field it
 * feeds — the reader's own question is the point, and these are a way in.
 */
export function FollowUps({
  items,
  onPick,
  className,
  boxed = false,
  pill = false,
}: {
  items: string[]
  onPick: (text: string) => void
  className?: string
  /** Draw each question as a bordered row rather than as a line of text. */
  boxed?: boolean
  /** Draw each question as a single clipped line in a rounded outline. */
  pill?: boolean
}) {
  if (items.length === 0) return null

  const outlined = boxed || pill

  return (
    <div className={cn("grid min-w-0 grid-cols-[minmax(0,1fr)]", pill ? "gap-2" : boxed ? "gap-1.5" : "gap-5", className)}>
      {items.map((item, index) => (
        <button
          key={`${index}-${item}`}
          type="button"
          onClick={() => onPick(item)}
          className={cn(
            "flex min-w-0 text-left text-row text-ink-3 transition-colors hover:text-foreground",
            pill &&
              "items-center gap-[0.7rem] rounded-pill border border-border px-4 py-[0.68rem] hover:border-ink-6 hover:bg-surface-raised",
            boxed &&
              "items-start gap-2.5 rounded-card border border-border px-2.5 py-2 leading-[1.4] hover:bg-foreground/[0.045]",
            !outlined && "items-center gap-[0.85rem]",
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
          {/* Clipped rather than wrapped in a pill: a two-line pill loses the
              shape that makes it read as one offer among several. */}
          <span className={cn("min-w-0", pill && "truncate")}>{item}</span>
        </button>
      ))}
    </div>
  )
}
