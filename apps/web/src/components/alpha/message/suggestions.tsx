"use client"

import { CornerDownRight } from "lucide-react"

import { PROGRESS_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/**
 * What the reader might ask next, offered rather than asked.
 *
 * Pressing one **fills the composer and does not send it** — the same contract
 * a question offered by a panel has (`shell-state`, `ask`). A suggestion that
 * sent itself would spend a Turn the reader had not decided to spend, and these
 * are generated text: worth offering, not worth acting on unread.
 *
 * Rendered only under the newest answer. Every answer in a long Thread carrying
 * its own five would turn the transcript into a page of prompts with the
 * conversation between them.
 */
export function Suggestions({
  questions,
  onAsk,
  className,
}: {
  questions: string[]
  onAsk: (question: string) => void
  className?: string
}) {
  if (questions.length === 0) return null

  return (
    <section className={cn("grid gap-1", className)} aria-label={PROGRESS_COPY.suggestionsTitle}>
      <h3 className="pb-1 text-[0.95rem] text-ink-3">{PROGRESS_COPY.suggestionsTitle}</h3>
      <ul className="grid">
        {questions.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onAsk(question)}
              className="flex w-full items-start gap-2.5 rounded-lg px-1 py-2 text-left text-[0.95rem] text-ink-4 transition-colors hover:text-ink-1"
            >
              <CornerDownRight
                className="mt-1 size-3.5 shrink-0 text-ink-6"
                strokeWidth={1.6}
                aria-hidden
              />
              <span className="min-w-0 flex-1">{question}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
