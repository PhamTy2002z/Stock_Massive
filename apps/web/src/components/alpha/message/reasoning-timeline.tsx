"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { Loader2 } from "lucide-react"

import { toolCallEmptyLabel, toolCallErrorLabel } from "@/lib/alpha-desk/copy"
import { signalIssueSentence } from "@/lib/signal-issues"
import {
  answeredNothing,
  distinctDomains,
  outcomeIssue,
  toolCallKind,
  type Thought,
  type ToolCall,
} from "@/lib/alpha-desk/types"
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
 * **It always ends in a row that is moving, while the Turn is running.** A tool
 * call carries its own spinner for as long as it is out, so the rail is alive
 * until the last call returns and then goes completely still — through the whole
 * stretch where the model is deciding what to do next, or writing the answer,
 * which on a hard question is most of the wait. Nothing moving reads as nothing
 * happening. The seconds go in the fold's own line instead of in that row,
 * because the line is the half that survives a reader folding the rail shut.
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
        {running ? workingLabel(seconds) : `Đã làm việc trong ${seconds}s`}
        <ChevronIcon open={open} />
      </button>

      {/* The fold. `duration-300` and the `visibility` transition below are
          `TIMELINE_FOLD_MS` in `reveal.ts`, which is what the answer waits for
          before it starts growing underneath.

          Animated by grid rows rather than by height, because the content has
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
            // The live row below is the last one whenever there is one, so a
            // trace that is still growing keeps its connecting line.
            const isLast = !running && index === items.length - 1
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

          {/* The one row that says the Turn has not stopped. A tool call spins
              while it runs, so the rail looks alive right up to the moment the
              last call returns — and then looks finished, for however long the
              model spends deciding what to do next or writing the answer. That
              stretch is most of the wait on a hard question, and a rail with
              nothing moving in it reads as a Turn that died. */}
          {running && (
            <RailRow icon={<WorkingDots />} isLast>
              <span
                role="status"
                className="text-meta leading-[22px] text-muted-foreground"
              >
                {items.length === 0 ? "Đang chuẩn bị…" : "Đang xử lý…"}
              </span>
            </RailRow>
          )}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * What the fold's own line says while the Turn is running.
 *
 * The seconds go here rather than in the row below, because this is the half
 * that survives the reader folding the rail shut — and because a timer next to
 * the words `Đang làm việc` is the same sentence the finished state ends on,
 * rather than a second one. Under a second there is no figure worth printing.
 */
function workingLabel(seconds: number): string {
  return seconds > 0 ? `Đang làm việc · ${seconds}s` : "Đang làm việc…"
}

/**
 * Three dots keeping time, as the rail's live icon.
 *
 * The design's own pulse (`vg-dot-pulse`) rather than another spinner: a
 * spinner is what a single tool call uses while it waits for an answer, and
 * this is not waiting on anything in particular. Staggered by an inline delay,
 * which is also what makes it read as travelling left to right.
 */
function WorkingDots() {
  return (
    <span className="flex items-center gap-[3px]" aria-hidden>
      {[0, 160, 320].map((delay) => (
        <span
          key={delay}
          style={{ animationDelay: `${delay}ms` }}
          className="size-[3px] rounded-full bg-current animate-vg-dot-pulse"
        />
      ))}
    </span>
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

/**
 * How many publishers one finished lookup came back with, and which ones.
 *
 * **Distinct publishers, not results.** A search returning five pages from two
 * newspapers rested on two sources, and drawing five marks would tell a reader
 * the answer was corroborated two and a half times more than it was. The count
 * beside them is the same number for the same reason.
 *
 * The hostnames are the backend's own (`results[].source`), so nothing here
 * parses a link a second time. They reach the screen as text and as marks and
 * never as markup: every one of these strings was written by somebody else, and
 * the rule that holds for the source list holds for a line beside a spinner.
 *
 * The full list rides in `title` because the marks are a glance and a glance is
 * not readable. Three discs say *it went and looked, at these sorts of places*;
 * the names say which, without the row having to grow to hold them.
 */
function SourceTally({ call }: { call: ToolCall }) {
  const domains = distinctDomains([call])
  // A call that reports a count but carries no projection of what it found —
  // a Turn stored before the sources travelled — keeps the sentence it always
  // had. Saying nothing there would be a row that ran and found nothing, which
  // is the opposite of what happened.
  if (domains.length === 0) {
    return call.result_count > 0 ? (
      <span className="ml-auto flex-none text-meta leading-[22px] text-muted-foreground">
        {call.result_count} kết quả
      </span>
    ) : null
  }

  return (
    <span
      className="ml-auto flex flex-none items-center gap-[0.55rem] text-meta leading-[22px] text-muted-foreground"
      title={domains.join(", ")}
    >
      {domains.length} nguồn
      <SourceChips sources={domains} />
    </span>
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
          found nothing, and only one of those is worth retrying. Which word it
          gets depends on the reason: a ceiling of ours refusing the call is not
          the same event as a page that would not load. */}
      {call.status === "error" && (
        <span className="ml-auto flex-none text-meta leading-[22px] text-destructive">
          {toolCallErrorLabel(call.error)}
        </span>
      )}
      {/* A call that ran and came back with nothing says so, in its own words.
          It is neither a failure nor a plain success: the tool worked, the
          question was well formed, and there was no number at the end of it.
          Drawn like a success it was invisible, and a third of the store reads
          in the trace were exactly this. The reason rides in the title, where
          the Signal Issue vocabulary already owns one sentence per code. */}
      {call.status === "ok" && answeredNothing(call) && (
        <span
          className="ml-auto flex-none text-meta leading-[22px] text-muted-foreground/70"
          title={emptyReason(call)}
        >
          {toolCallEmptyLabel(call.outcome)}
        </span>
      )}
      {/* A result count only where results are what came back. A store read
          answers with one figure and no sources, so "0 kết quả" beside a call
          that succeeded said the opposite of what happened. */}
      {call.status === "ok" && !answeredNothing(call) && toolCallKind(call) === "external" && (
        <SourceTally call={call} />
      )}
    </div>
  )

  return (
    <RailRow
      icon={running ? <Spinner /> : <CallIcon call={call} />}
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

/**
 * From how many calls a round arrives folded.
 *
 * One symbol's worth of a round is four figures, and those four stay on screen:
 * they are the work, and a reader watching one symbol being read can follow
 * them. A portfolio's worth is the same round times seven, and twenty-eight
 * near-identical lines are longer than the answer they were gathered for — at
 * that size the list is no longer telling the reader anything the count does
 * not. So the threshold sits above the single-symbol round and below the
 * portfolio one.
 */
const GROUP_FOLD_FROM = 7

/**
 * A round with two or more tool calls: one header, and the calls branching off it.
 *
 * Drawn as a tree rather than as a second flat list, because the calls *are*
 * subordinate to the header — they are the one decision it names, broken out.
 * A dozen rows each carrying their own icon read as a dozen peers of the line
 * above them, which is both wrong and, at a dozen, most of the rail's height.
 * The branch glyph is the one the follow-up questions use, so a reader meets the
 * same mark for the same idea in both places.
 *
 * **The kind icon moves to the header where every call shares one.** Repeating
 * it down the branch says nothing after the first row. A round that mixed a
 * search with a store read has no single kind to state up there, so in that one
 * case each branch keeps its own.
 *
 * **Past `GROUP_FOLD_FROM` calls the branch list arrives folded**, and the
 * header carries what folding it away would otherwise have taken with it: how
 * many of the calls are back, and how many failed. Neither is in the count on
 * its own, and both are things a reader watching a portfolio being read is
 * actually waiting on — the header stays a sentence about the work rather than
 * becoming a lid over it.
 *
 * Whether it is open is derived rather than stored, so a round that grows past
 * the threshold as its calls arrive folds itself without an effect to resync:
 * the stream announces a round's calls one at a time, so a state initialised on
 * the first of them would have been initialised on a group of one.
 */
function GroupRow({ calls, isLast }: { calls: ToolCall[]; isLast: boolean }) {
  const [pressed, setPressed] = useState<boolean | null>(null)
  const anyRunning = calls.some((call) => call.status === "running")
  const allStore = calls.every((call) => toolCallKind(call) === "store")
  const mixed = !allStore && calls.some((call) => toolCallKind(call) === "store")

  // A press always wins, for as long as this round is on screen. Nothing else
  // reopens it: the count only ever grows, so a group that folded itself cannot
  // unfold under a reader who left it shut.
  const open = pressed ?? calls.length < GROUP_FOLD_FROM
  const settled = calls.filter((call) => call.status !== "running").length
  const failed = calls.filter((call) => call.status === "error").length

  return (
    <RailRow
      icon={anyRunning ? <Spinner /> : allStore ? <ChartIcon /> : <SearchIcon />}
      isLast={isLast}
    >
      <button
        type="button"
        onClick={() => setPressed(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-[0.55rem] text-left text-meta leading-[22px] text-muted-foreground transition-colors hover:text-ink-2"
      >
        {/* A store read is not a query against anything outside, and calling a
            dozen of them "truy vấn" borrowed the wrong word for the work. */}
        <span className="min-w-0">
          {allStore ? `Đọc ${calls.length} chỉ báo` : `Đã chạy ${calls.length} truy vấn`}
        </span>
        {/* Only while the rows that would say it themselves are folded away. */}
        {!open && anyRunning && (
          <span className="flex-none tabular-nums">{`· ${settled}/${calls.length}`}</span>
        )}
        {!open && failed > 0 && (
          <span className="flex-none text-destructive">{`· ${failed} lỗi`}</span>
        )}
        <ChevronIcon open={open} />
      </button>
      {open && (
      <div className="mt-[11px] grid gap-[9px]">
        {calls.map((call) => (
          <div key={call.id} className="flex items-center gap-[0.55rem]">
            {call.status === "running" ? (
              <Spinner className="flex-none" />
            ) : (
              <BranchIcon className="flex-none text-muted-foreground/70" />
            )}
            {mixed && call.status !== "running" && (
              <CallIcon call={call} className="flex-none text-muted-foreground" />
            )}
            <span className="min-w-0 text-meta leading-[22px] text-muted-foreground">
              {call.summary}
            </span>
            {call.status === "error" && (
              <span className="flex-none text-meta leading-[22px] text-destructive">
                {toolCallErrorLabel(call.error)}
              </span>
            )}
            {call.status === "ok" && answeredNothing(call) && (
              <span
                className="flex-none text-meta leading-[22px] text-muted-foreground/70"
                title={emptyReason(call)}
              >
                {toolCallEmptyLabel(call.outcome)}
              </span>
            )}
            {/* The branch rows are where the parallel searches land, and they
                were the one place the count and the marks were missing: a round
                of three searches said what each one asked and nothing about what
                any of them found. */}
            {call.status === "ok" &&
              !answeredNothing(call) &&
              toolCallKind(call) === "external" && <SourceTally call={call} />}
          </div>
        ))}
      </div>
      )}
    </RailRow>
  )
}

/**
 * The sentence behind an empty answer, for the row's title attribute.
 *
 * Read out of `signalIssueSentence` rather than written here: that module holds
 * the one Vietnamese sentence per **Signal Issue** code, and a second copy of
 * any of them is the drift it exists to prevent. It already answers an unknown
 * code with a readable sentence rather than the code itself, so there is nothing
 * to guard here.
 */
function emptyReason(call: ToolCall): string {
  const issue = outcomeIssue(call)
  return issue === null ? toolCallEmptyLabel(call.outcome) : signalIssueSentence(issue)
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

/**
 * Which kind of evidence one call went and got.
 *
 * A globe for the open web, a chart for this system's own store. The backend
 * says which (`ToolCall.kind`), off the same declaration that decides whether
 * the result is wrapped as outside content — so the rail cannot draw a figure
 * out of our own Postgres the way it draws a stranger's page, which is the
 * distinction the whole evidence boundary rests on.
 */
function CallIcon({ call, className }: { call: ToolCall; className?: string }) {
  return toolCallKind(call) === "store" ? (
    <ChartIcon className={className} />
  ) : (
    <GlobeIcon className={className} />
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


/** A bar chart, for a figure read out of this system's own store. */
function ChartIcon({ className }: { className?: string }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M3 3v18h18" />
      <path d="M7 16v-5" />
      <path d="M12 16V7" />
      <path d="M17 16v-8" />
    </svg>
  )
}


/**
 * The mark on a row that hangs off the one above it.
 *
 * The same path the follow-up questions use, inlined here the way every other
 * icon in this file is — the class comment at the top says why the design's own
 * path data lives beside the component that draws it.
 */
function BranchIcon({ className }: { className?: string }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M5 5v9h11" />
      <polyline points="12 10 16 14 12 18" />
    </svg>
  )
}
