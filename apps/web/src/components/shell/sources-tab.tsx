"use client"

import { useState } from "react"
import { BarChart3, ChevronDown, ChevronRight, Globe, Lightbulb } from "lucide-react"

import { SourceList } from "@/components/alpha/message/source-list"
import { toolCallKind, type Thought, type ToolCall } from "@/lib/alpha-desk/types"
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
 *
 * **The two kinds of evidence are drawn apart.** A page and a figure out of this
 * system's own store are not the same kind of claim: the figure carries a date
 * and a health and reads the same tomorrow. The backend says which is which
 * (`ToolCall.kind`), and this panel gives them different icons, a different
 * count, and different grouping — a store read has no "results" to count, so a
 * `0` beside a successful one read as "found nothing".
 *
 * **A run of store reads collapses to one row.** A model answering about one
 * company asks for a dozen figures in a breath, and a dozen rows that differ
 * only in which figure was named is a panel a reader scrolls past rather than
 * reads. One line says how many, and opening it lists them. Searches stay one
 * row each: each has its own pages behind it, and those are the thing the reader
 * came to check.
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
          {runs(round.calls).map((run) =>
            run.kind === "store" && run.calls.length > 1 ? (
              <StoreRunRow key={run.calls[0].id} calls={run.calls} />
            ) : (
              run.calls.map((call) => <CallRow key={call.id} call={call} />)
            ),
          )}
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

/** One lookup, and its pages behind a disclosure where it has any. */
function CallRow({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false)
  const hasResults = call.results.length > 0
  const store = toolCallKind(call) === "store"

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
        <KindIcon store={store} />
        <span className="min-w-0 flex-1 text-meta text-muted-foreground">{call.summary}</span>
        {/* A count only where counting means something. A search has pages and
            the number of them is the reader's first question; a store read has
            one figure, and a `0` beside a call that succeeded read as "found
            nothing" — the opposite of what happened. */}
        {!store && (
          <span className="flex-none rounded-lg border border-border px-1.5 py-0.5 font-mono text-micro text-muted-foreground">
            {call.result_count}
          </span>
        )}
      </button>

      {open && hasResults && (
        <SourceList results={call.results} className="border-0 bg-transparent p-0 pb-4 pl-8" />
      )}
    </div>
  )
}

/**
 * Several store reads from one round, as one row that opens.
 *
 * The rows underneath carry no icon of their own: they are all the same kind by
 * construction, and repeating one icon a dozen times down a narrow panel is
 * noise rather than information.
 */
function StoreRunRow({ calls }: { calls: ToolCall[] }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border-y border-border">
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 px-1 py-3 text-left transition-opacity hover:opacity-75"
      >
        <span className="flex-none pt-px text-muted-foreground">
          {open ? (
            <ChevronDown className="size-[15px]" strokeWidth={1.8} />
          ) : (
            <ChevronRight className="size-[15px]" strokeWidth={1.8} />
          )}
        </span>
        <KindIcon store />
        <span className="min-w-0 flex-1 text-meta text-muted-foreground">
          Đọc {calls.length} chỉ báo từ dữ liệu hệ thống
        </span>
      </button>

      {open && (
        <ul className="grid gap-[9px] pb-4 pl-8">
          {calls.map((call) => (
            <li key={call.id} className="text-meta text-muted-foreground">
              {call.summary}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Which kind of evidence this row is about.
 *
 * A globe for the open web and a chart for this system's own store. The icon is
 * the fastest read on the row, so it is where the distinction belongs: a globe
 * on a figure out of our own Postgres told the reader the opposite of the truth.
 */
function KindIcon({ store }: { store: boolean }) {
  const Icon = store ? BarChart3 : Globe
  return (
    <Icon className="size-[15px] flex-none pt-px text-muted-foreground" strokeWidth={1.5} />
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
interface Run {
  kind: "external" | "store"
  calls: ToolCall[]
}

/**
 * One round's calls split into consecutive stretches of the same kind.
 *
 * Consecutive rather than sorted, so the order the model actually asked in
 * survives: a round that read three figures, searched, then read two more is
 * three runs, and reordering it into "all reads then all searches" would
 * describe work that did not happen.
 */
function runs(calls: ToolCall[]): Run[] {
  const grouped: Run[] = []
  for (const call of calls) {
    const kind = toolCallKind(call)
    const last = grouped.at(-1)
    if (last !== undefined && last.kind === kind) last.calls.push(call)
    else grouped.push({ kind, calls: [call] })
  }
  return grouped
}

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
