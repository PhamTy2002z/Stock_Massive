"use client"

/**
 * The state the surface had no way to show: a picture being built.
 *
 * Between the model choosing a Study and the row landing there is a stretch of
 * seconds where the pane held nothing at all and the composer said only that a
 * Turn was running. A reader who had just switched the desk on watched an empty
 * workspace and had no way to tell "working" from "this asked for nothing".
 *
 * **One piece of state drives two places.** The pill in the composer and the
 * skeleton in the pane are the same fact — a Study is in flight — so both read
 * `buildingLabel`, and neither computes it. Two derivations of one truth is how
 * a pill that says "Đang dựng…" ends up over a pane that says nothing is
 * happening.
 *
 * **A call is pending until its round has drawn something.** Not until it
 * reports `ok`: the desk view and the call's outcome arrive on the same stream and
 * the order between them is the backend's business. `round` is what the two
 * already share — the tool call carries the round that asked, and the
 * announcement carries the round that produced it — so a round with a desk view in
 * it is a round that is no longer building. That is also what makes this clear
 * on `signal_desk.ready` without anybody watching for the event.
 *
 * A settled Turn is never building. That is the second half of the guarantee:
 * a Turn that failed, was cancelled or simply finished without drawing anything
 * leaves no skeleton spinning behind it.
 */

import { isSettled, type LiveTurn } from "@/lib/alpha-desk/live-turn"
import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/**
 * The three tools that draw.
 *
 * Named rather than derived, because "does this tool produce a desk view" is not
 * something the tool call carries — `kind` says where the evidence came from,
 * not what it becomes. The list is short and the registry is the other side of
 * it; a fourth drawing tool adds a line here.
 */
const SIGNAL_DESK_TOOLS: ReadonlySet<string> = new Set([
  "run_study",
  "get_series",
  "render_signal_desk",
])

/**
 * What the surface should say it is building, or null when it is not.
 *
 * The tool call's own `summary` when it has one, because the backend writes it
 * and only the side that made the call knows which Study was chosen. The
 * generic line is the fallback rather than the default.
 */
export function buildingLabel(live: LiveTurn): string | null {
  if (isSettled(live)) return null
  const drawn = new Set(live.deskViews.map((deskView) => deskView.round))
  const pending = live.toolCalls.find(
    (call) =>
      SIGNAL_DESK_TOOLS.has(call.name) && call.status === "running" && !drawn.has(call.round),
  )
  if (pending === undefined) return null
  const summary = pending.summary.trim()
  return summary === "" ? SIGNAL_DESK_COPY.building : summary
}

/**
 * The shape of a desk view, held while the numbers are on their way.
 *
 * Deliberately the *design's* proportions rather than a spinner: a headline
 * band, three figures across, and the chart under them is what almost every
 * Study lays out, so the pane settles into the picture instead of jumping into
 * it. The blocks are inert scenery — `aria-hidden` — and the one thing a screen
 * reader is told is the line above them, which is the only part that carries
 * information.
 */
export function SignalDeskBuilding({ label }: { label: string }) {
  return (
    <div className="grid gap-3.5 animate-vg-fade-in">
      <p
        aria-live="polite"
        className="flex items-center gap-2.5 font-mono text-[0.86rem] text-ink-6"
      >
        <span
          aria-hidden
          className="block size-1.5 rounded-full bg-floor animate-vg-dot-pulse"
        />
        {label}
      </p>
      <Block className="h-[60px]" />
      <div className="grid grid-cols-3 gap-3">
        <Block className="h-24" delay="0.1s" />
        <Block className="h-24" delay="0.2s" />
        <Block className="h-24" delay="0.3s" />
      </div>
      <Block className="h-[260px]" delay="0.15s" />
    </div>
  )
}

/**
 * One placeholder.
 *
 * Staggered by an inline delay rather than by five utility classes: the offsets
 * are a property of this one arrangement, and the alternative is a Tailwind
 * safelist entry per block.
 */
function Block({ className, delay }: { className: string; delay?: string }) {
  return (
    <div
      aria-hidden
      style={delay === undefined ? undefined : { animationDelay: delay }}
      className={cn(
        "animate-pulse rounded-xl bg-surface-raised motion-reduce:animate-none",
        className,
      )}
    />
  )
}
