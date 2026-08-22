"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Globe, Lightbulb } from "lucide-react"

import { SourceList } from "@/components/alpha/message/source-list"
import type { Thought, ToolCall } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { useShell } from "./shell-state"

/**
 * Everything one answer rested on, beside the answer.
 *
 * The same facts the timeline shows, laid out for a different reader. The
 * timeline is read *while waiting* and is therefore terse and folded away; this
 * is read *afterwards*, by somebody checking the answer, so every search is
 * listed with its result count and every page is one open row away.
 *
 * It reads the transcript rather than holding its own copy. The shell remembers
 * only *which* answer is being examined, so a message that is refetched or
 * flagged keeps one version of itself, and this panel cannot drift from the
 * conversation it is describing.
 *
 * A search with no results still gets a row. The reader asked what the answer
 * rested on, and "this search came back empty" is part of that answer — hiding
 * it would make the work look tidier than it was.
 */
export function SourcesTab() {
  const { state } = useShell()
  const desk = useDesk()

  const entry = desk.entries.find(
    (candidate) =>
      candidate.kind === "assistant" && candidate.messageId === state.sourcesMessageId,
  )

  if (entry === undefined || entry.kind !== "assistant") {
    return (
      <p className="px-1 py-2 text-meta text-muted-foreground">
        Câu trả lời này không còn trong hội thoại đang mở.
      </p>
    )
  }

  const { thoughts, toolCalls } = entry.view
  if (thoughts.length === 0 && toolCalls.length === 0) {
    return (
      <p className="px-1 py-2 text-meta text-muted-foreground">
        Câu trả lời này không tra cứu gì.
      </p>
    )
  }

  return (
    <div>
      {rounds(thoughts, toolCalls).map((round) => (
        <div key={round.index}>
          {round.thought !== null && <ThoughtRow text={round.thought.text} />}
          {round.calls.map((call) => (
            <CallRow key={call.id} call={call} />
          ))}
        </div>
      ))}
    </div>
  )
}

/** One line of what the model said it was about to do. */
function ThoughtRow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-[0.7rem] px-1 py-3.5">
      <Lightbulb className="size-[15px] flex-none text-muted-foreground" strokeWidth={1.5} />
      <span className="text-pretty text-meta font-semibold text-ink-1">{text}</span>
    </div>
  )
}

/** One search, and its pages behind a disclosure. */
function CallRow({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false)
  const hasResults = call.results.length > 0

  return (
    <div className="border-y border-border">
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        disabled={!hasResults}
        aria-expanded={hasResults ? open : undefined}
        className={cn(
          "flex w-full items-start gap-2 px-1 py-3 text-left transition-opacity",
          hasResults ? "hover:opacity-75" : "cursor-default",
        )}
      >
        <span className="flex-none pt-px text-muted-foreground">
          {hasResults ? (
            open ? (
              <ChevronDown className="size-[15px]" strokeWidth={1.8} />
            ) : (
              <ChevronRight className="size-[15px]" strokeWidth={1.8} />
            )
          ) : (
            // A placeholder of the same width, so a row with nothing to open
            // lines up with the rows that do rather than shifting left.
            <span className="block size-[15px]" />
          )}
        </span>
        <Globe className="size-[15px] flex-none pt-px text-muted-foreground" strokeWidth={1.5} />
        <span className="min-w-0 flex-1 text-meta text-muted-foreground">{call.summary}</span>
        <span className="flex-none rounded-lg border border-border px-1.5 py-0.5 font-mono text-micro text-muted-foreground">
          {call.result_count}
        </span>
      </button>

      {open && hasResults && (
        <SourceList results={call.results} className="border-0 bg-transparent p-0 pb-4 pl-8" />
      )}
    </div>
  )
}

interface Round {
  index: number
  thought: Thought | null
  calls: ToolCall[]
}

/**
 * The Turn's work grouped by the round it happened in, in order.
 *
 * The round is the backend's own number, so this groups rather than guesses:
 * the several searches a model asks for at once were one decision, and the
 * sentence introducing them belongs above all of them.
 */
function rounds(thoughts: Thought[], toolCalls: ToolCall[]): Round[] {
  const indices = new Set<number>()
  for (const thought of thoughts) indices.add(thought.round)
  for (const call of toolCalls) indices.add(call.round)

  return [...indices]
    .sort((left, right) => left - right)
    .map((index) => ({
      index,
      thought: thoughts.find((thought) => thought.round === index) ?? null,
      calls: toolCalls.filter((call) => call.round === index),
    }))
}
