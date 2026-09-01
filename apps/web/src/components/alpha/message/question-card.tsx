"use client"

import { Check } from "lucide-react"

import { QUESTION_COPY } from "@/lib/alpha-desk/copy"
import type { QuestionPart } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * One question a Turn ended by asking, and the two ways out of it.
 *
 * **A card is not a door.** The Turn that asked has already ended, so nothing is
 * waiting on this: pressing an option records a choice the next Turn can read,
 * skipping records that the reader declined and the work runs on stated
 * assumptions, and typing another question instead supersedes it. Every one of
 * the four states it can be in is drawn, because a card that vanished once it
 * was settled would leave a transcript where the answer below refers to a
 * question nobody can see.
 *
 * **Every word in it is the backend's.** The prompt, the labels, the one line
 * under a label and the skip label were written where the question was decided;
 * this component composes none of them. What it owns is the frame and the states
 * — which is also why a settled card keeps its options on screen, dimmed and
 * inert, with the choice marked: the reader is being shown what was asked and
 * what they did, not offered it again.
 *
 * Single choice only, for now. `multi_select` is carried from the first version
 * because it is a fact about the question rather than about a surface, and one
 * choice is a valid answer to either kind — so the flag can wait for the surface
 * that offers it without any question already stored having to be guessed at.
 */
export function QuestionCard({
  question,
  onAnswer,
  onSkip,
  className,
}: {
  question: QuestionPart
  /** Absent where there is nowhere to send a choice, which draws the card inert. */
  onAnswer?: (questionId: string, selectedOptionIds: string[]) => void
  onSkip?: (questionId: string) => void
  className?: string
}) {
  const pending = question.state === "pending"
  // Conditional on the handlers as well as on the state, the way the message
  // actions are: a control with nowhere to send the press is worse than none.
  const answerable = pending && onAnswer !== undefined
  const chosen = new Set(question.selected_option_ids ?? [])

  return (
    <section
      aria-label={QUESTION_COPY.region}
      className={cn(
        "grid gap-2.5 rounded-card border border-border px-3.5 py-3",
        !pending && "opacity-60",
        className,
      )}
    >
      <p className="text-row leading-[1.45] text-foreground">{question.prompt}</p>

      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1.5">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            disabled={!answerable}
            onClick={() => onAnswer?.(question.question_id, [option.id])}
            className={cn(
              "flex min-w-0 items-start gap-2.5 rounded-card border border-border px-2.5 py-2 text-left text-row leading-[1.4] text-ink-3 transition-colors",
              answerable && "hover:bg-foreground/[0.045] hover:text-foreground",
              // Inert rather than removed: `disabled:opacity-50` on top of a
              // card that is already dimmed would put the words below what is
              // readable, so the row keeps its weight and loses only the hover.
              !answerable && "cursor-default",
              chosen.has(option.id) && "border-ink-6 text-foreground",
            )}
          >
            {chosen.has(option.id) && (
              <Check className="mt-0.5 size-3.5 flex-none text-muted-foreground" />
            )}
            <span className="min-w-0">
              {option.label}
              {option.detail !== null && (
                <span className="block text-meta text-muted-foreground">
                  {option.detail}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>

      {/* Skipping is a choice with an outcome, so it is a control and not an
          absence — but a quieter one than the options, because the card exists
          to be answered. */}
      {pending && onSkip !== undefined && (
        <button
          type="button"
          onClick={() => onSkip(question.question_id)}
          className="justify-self-start text-meta text-muted-foreground underline underline-offset-2 transition-colors hover:text-ink-2"
        >
          {question.skip_label === "" ? QUESTION_COPY.skip : question.skip_label}
        </button>
      )}

      {/* What became of it, in one line, for the three states that are ends. An
          answered card says so beside the mark on the option itself; the other
          two have nothing marked, so the line is the only thing that can say
          the question was left rather than overlooked. */}
      {!pending && (
        <p className="text-meta text-muted-foreground">{settledLine(question)}</p>
      )}
    </section>
  )
}

/** The one line under a card that is no longer answerable. */
function settledLine(question: QuestionPart): string {
  if (question.state === "skipped") return QUESTION_COPY.skipped
  if (question.state === "superseded") return QUESTION_COPY.superseded
  const chosen = question.selected_option_ids ?? []
  const labels = question.options
    .filter((option) => chosen.includes(option.id))
    .map((option) => option.label)
  // An answered card whose choice is not among its own options is a card and a
  // row that disagree. The state is still the truth about what happened, so the
  // line says the question was answered rather than inventing which way.
  return labels.length === 0
    ? QUESTION_COPY.answered
    : `${QUESTION_COPY.answered}: ${labels.join(", ")}`
}
