"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { Loader2 } from "lucide-react"

import { TOOL_CALL_COPY } from "@/lib/alpha-desk/copy"
import type { Thought, ToolCall } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { SourceChips } from "./source-chips"
import { SourceList } from "./source-list"

/**
 * What a Turn did on its way to the answer, collapsed to one line.
 *
 * Open by default while `running` is true, because a reader watching a Turn
 * in progress is watching *this* — it is the only visible sign that anything
 * is happening before the first delta lands. Collapsed by default once it is
 * done, because at that point it is a receipt nobody asked to keep reading,
 * and the thing the reader came for is the prose below it. Either way the
 * button is the one source of truth for open/closed: a press always wins
 * until the next run/finish transition resets it, so a reader who opened it
 * mid-run to watch does not have it slammed shut under them by an unrelated
 * re-render.
 *
 * Grouping tool calls by `round` rather than by arrival order is the point of
 * carrying `round` on `ToolCall` at all — the model asks for several searches
 * in one breath, and a client re-deriving groups from timing would be
 * guessing at a fact the backend already knows. A round with two or more
 * calls collapses to "Đã chạy N truy vấn" with the calls listed under it,
 * because a reader does not need N separate rows to learn the model looked at
 * N things at once; a round with exactly one stays a single row, and that one
 * gets the result count and source stack the design gives a single lookup —
 * a group of unrelated queries does not get one card per query fighting for
 * the same space.
 */
export function ReasoningTimeline({
  thoughts,
  toolCalls,
  elapsedMs,
  running,
  className,
}: {
  thoughts: Thought[]
  toolCalls: ToolCall[]
  elapsedMs: number
  running: boolean
  className?: string
}) {
  const [open, setOpen] = useState(running)

  // The one resync point: a run→finish or finish→run transition sets the
  // default state again. Anything the reader did with the button in between
  // is respected until the next transition, never overwritten by an
  // unrelated re-render that leaves `running` itself unchanged.
  useEffect(() => {
    setOpen(running)
  }, [running])

  const items = useMemo(() => buildRailItems(thoughts, toolCalls), [thoughts, toolCalls])

  if (!running && items.length === 0) return null

  const seconds = Math.max(0, Math.round(elapsedMs / 1000))

  return (
    <div className={cn(className)}>
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        className="flex items-center gap-[0.4rem] text-meta text-muted-foreground transition-colors hover:text-ink-2"
      >
        {running ? "Đang làm việc…" : `Đã làm việc trong ${seconds}s`}
        <ChevronIcon open={open} />
      </button>

      {/* Animated by grid rows rather than by height, because the content has
          no height anybody can name: it grows by whole rows while the Turn
          runs. A grid track going 0fr→1fr resolves to the content's own height
          at both ends, so the fold is smooth without measuring anything and
          without a fixed max-height that would clip a long trace.

          `items.length > 0` is deliberately *not* a condition on rendering the
          wrapper: the collapse has to animate on the way out too, and a branch
          that unmounted the rows would cut it off halfway. */}
      <div
        aria-hidden={!open}
        className={cn(
          "grid transition-[grid-template-rows,opacity] duration-300 ease-out motion-reduce:transition-none",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        )}
      >
        {/* The row that is actually animated. `min-h-0` lets it shrink below
            its content, which is the whole reason the trick works.

            `visibility` is what takes the folded rows out of the tab order —
            zero height does not, so without it the reader would tab into
            buttons they cannot see. It flips only once the fold has finished,
            or the rows would vanish instead of collapsing; on the way open it
            flips immediately, or they would animate in invisibly. */}
        <div
          className={cn(
            "min-h-0 overflow-hidden",
            open
              ? "visible [transition:visibility_0s_linear_0s]"
              : "invisible [transition:visibility_0s_linear_300ms]",
            "motion-reduce:[transition:none]",
          )}
        >
          <div className="mt-[10px]">
          {items.map((item, index) => {
            const isLast = index === items.length - 1
            if (item.kind === "thought") {
              return (
                <RailRow key={item.key} icon={<BulbIcon />} isLast={isLast}>
                  <span className="text-meta leading-[22px] text-muted-foreground">
                    {item.text}
                  </span>
                </RailRow>
              )
            }
            if (item.kind === "single") {
              return <SingleCallRow key={item.key} call={item.call} isLast={isLast} />
            }
            return <GroupRow key={item.key} calls={item.calls} isLast={isLast} />
          })}
          </div>
        </div>
      </div>
    </div>
  )
}

type RailItem =
  | { kind: "thought"; key: string; text: string }
  | { kind: "single"; key: string; call: ToolCall }
  | { kind: "group"; key: string; calls: ToolCall[] }

/**
 * Thoughts before the calls they introduced, rounds ascending — the order the
 * work actually happened in, read back out of two arrays the backend keeps
 * separate because a thought is prose the reply must never absorb.
 */
function buildRailItems(thoughts: Thought[], toolCalls: ToolCall[]): RailItem[] {
  const rounds = new Set<number>()
  for (const thought of thoughts) rounds.add(thought.round)
  for (const call of toolCalls) rounds.add(call.round)

  const items: RailItem[] = []
  for (const round of Array.from(rounds).sort((a, b) => a - b)) {
    thoughts
      .filter((thought) => thought.round === round)
      .forEach((thought, index) => {
        items.push({ kind: "thought", key: `thought-${round}-${index}`, text: thought.text })
      })

    const calls = toolCalls.filter((call) => call.round === round)
    if (calls.length >= 2) {
      items.push({ kind: "group", key: `group-${round}`, calls })
    } else if (calls.length === 1) {
      items.push({ kind: "single", key: `single-${round}`, call: calls[0] })
    }
  }
  return items
}

/**
 * One row of the rail: an icon over a connecting line, and its content beside
 * it. `isLast` drops both the line and the row's own bottom padding, because a
 * line that dangled past the final icon would look like the timeline expects
 * another row that never draws.
 */
function RailRow({
  icon,
  isLast,
  children,
}: {
  icon: ReactNode
  isLast: boolean
  children: ReactNode
}) {
  return (
    <div className="grid grid-cols-[19px_1fr] gap-x-[13px]">
      <div className="flex flex-col items-center gap-[5px]">
        <span className="flex h-[22px] flex-none items-center justify-center text-muted-foreground">
          {icon}
        </span>
        {!isLast && <span className="min-h-[12px] w-px flex-1 bg-border" />}
      </div>
      <div className={cn("min-w-0", isLast ? "pb-0" : "pb-[14px]")}>{children}</div>
    </div>
  )
}

/** A round with exactly one tool call: its own row, its own result count. */
function SingleCallRow({ call, isLast }: { call: ToolCall; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const running = call.status === "running"
  const hasResults = call.results.length > 0

  const row = (
    <div className="flex items-start gap-4">
      <span className="min-w-0 flex-1 text-meta leading-[22px] text-muted-foreground">
        {call.summary}
      </span>
      {/* A call that failed says so instead of reporting nought results. The
          design has no failure state because its data never fails; leaving one
          out would draw a call that returned nothing exactly like a call that
          found nothing, and only one of those is worth retrying. */}
      {call.status === "error" && (
        <span className="ml-auto flex-none text-meta leading-[22px] text-destructive">
          {TOOL_CALL_COPY.error}
        </span>
      )}
      {call.status === "ok" && (
        <span className="ml-auto flex flex-none items-center gap-[0.55rem] text-meta leading-[22px] text-muted-foreground">
          {call.result_count} kết quả
          <SourceChips sources={call.results.map((result) => result.source)} />
        </span>
      )}
    </div>
  )

  return (
    <RailRow
      icon={running ? <Spinner /> : <GlobeIcon />}
      isLast={isLast}
    >
      {hasResults ? (
        <button
          type="button"
          onClick={() => setExpanded((was) => !was)}
          aria-expanded={expanded}
          className="block w-full text-left transition-opacity hover:opacity-80"
        >
          {row}
        </button>
      ) : (
        row
      )}

      {expanded && hasResults && (
        <SourceList results={call.results} className="mb-[3px] mt-[11px] max-h-[330px]" />
      )}
    </RailRow>
  )
}

/** A round with two or more tool calls: one header, one plain row per call. */
function GroupRow({ calls, isLast }: { calls: ToolCall[]; isLast: boolean }) {
  const anyRunning = calls.some((call) => call.status === "running")

  return (
    <RailRow icon={anyRunning ? <Spinner /> : <SearchIcon />} isLast={isLast}>
      <span className="text-meta leading-[22px] text-muted-foreground">
        Đã chạy {calls.length} truy vấn
      </span>
      <div className="mt-[11px] grid gap-[9px]">
        {calls.map((call) => (
          <div key={call.id} className="flex items-center gap-[0.55rem]">
            {call.status === "running" ? (
              <Spinner className="flex-none" />
            ) : (
              <GlobeIcon className="flex-none text-muted-foreground" />
            )}
            <span className="min-w-0 text-meta leading-[22px] text-muted-foreground">
              {call.summary}
            </span>
            {call.status === "error" && (
              <span className="flex-none text-meta leading-[22px] text-destructive">
                {TOOL_CALL_COPY.error}
              </span>
            )}
          </div>
        ))}
      </div>
    </RailRow>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <Loader2
      className={cn("size-[15px] animate-spin text-muted-foreground motion-reduce:animate-none", className)}
    />
  )
}

/** Copied from the design's own path data — see the class comment at the top. */
function BulbIcon({ className }: { className?: string }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={className}
      aria-hidden
    >
      <path d="M9 15.4a5 5 0 1 1 6 0v1.3h-6z" />
      <path d="M10 19.6h4" />
    </svg>
  )
}

function GlobeIcon({ className }: { className?: string }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={className}
      aria-hidden
    >
      <circle cx="12" cy="12" r="8" />
      <path d="M4 12h16" />
      <path d="M12 4c2.6 3 2.6 13 0 16-2.6-3-2.6-13 0-16z" />
    </svg>
  )
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={className}
      aria-hidden
    >
      <circle cx="11" cy="11" r="6" />
      <line x1="15.4" y1="15.4" x2="20" y2="20" />
    </svg>
  )
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      aria-hidden
      className={cn(
        "transition-transform duration-300 ease-out motion-reduce:transition-none",
        open && "-rotate-180",
      )}
    >
      {/* One chevron that turns, rather than two that swap: the swap reads as
          a flicker beside a panel that is itself gliding. */}
      <polyline points="7 10 12 15 17 10" />
    </svg>
  )
}
