"use client"

/**
 * The board before there is a board.
 *
 * A pane that said only "ask something" was answering the wrong question. The
 * reader who has just switched the desk on knows they have to ask; what they
 * cannot know is what asking will *get* them — and that is the one thing an
 * empty workspace is well placed to show. So the state has four parts, in the
 * order the reader reads them: the shape of a board, the fact that the desk is
 * on, what will fill it, and what it can be asked about.
 *
 * **The ghost is a drawing, not a skeleton.** `SignalDeskPanel`'s skeleton means
 * "numbers are on their way" and pulses to say so. This one means "a board looks
 * like this" — nothing is loading, so it does not pulse, it is dashed rather
 * than filled, and it is `aria-hidden`: a reader on a screen reader gains
 * nothing from three grey rectangles and would have to listen past them to
 * reach the sentence that matters.
 *
 * **One amber bar, and it is the only accent here.** The rest of the ghost is
 * ink at low alpha. A board's whole job is to put one figure in front of the
 * reader, and the ghost says that with its geometry rather than with a caption.
 *
 * No button. The composer is the call to action, in the column to the left, and
 * a second one here would send the reader hunting for a control already under
 * their hands.
 */

import { Info } from "lucide-react"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"

/** The heights of the ghost's bars, and which one carries the accent. */
const GHOST_BARS = [36, 52, 30, 64, 100, 58, 40, 26]
const GHOST_ACCENT = 100

export function SignalDeskEmpty() {
  return (
    <div className="m-auto flex w-full max-w-[460px] animate-vg-fade-in flex-col items-center">
      <GhostBoard />

      <div className="flex items-center gap-[0.45rem] font-mono text-micro text-ink-6">
        {/* The dot pulses and the words do not: a reader glancing back at a pane
            they left open needs to see that the desk is still armed, and the
            only thing on this screen that can carry "still" is motion. */}
        <span
          aria-hidden
          className="block size-1.5 animate-vg-live-pulse rounded-full bg-positive motion-reduce:animate-none"
        />
        {SIGNAL_DESK_COPY.emptyStatus}
      </div>

      <h3 className="mt-3 text-balance text-center font-serif text-[1.9rem] font-light leading-[1.15] tracking-[-0.02em] text-ink-display">
        {SIGNAL_DESK_COPY.emptyTitle}
      </h3>

      <p className="mt-2.5 max-w-[42ch] text-center text-control leading-[1.55] text-ink-6 [text-wrap:pretty]">
        {SIGNAL_DESK_COPY.emptyBody}
      </p>

      <p className="mt-7 flex items-center justify-center gap-[0.45rem] text-center text-meta leading-[1.5] text-ink-6">
        <Info className="size-[13px] flex-none" strokeWidth={1.6} aria-hidden />
        {SIGNAL_DESK_COPY.emptyUniverseHint}
      </p>
    </div>
  )
}

/**
 * What a board looks like, at a glance and with nothing in it.
 *
 * Three tiles over a bar series, because that is the shape every registered
 * Study actually produces — a headline figure or two, then a distribution. It is
 * a promise the desk can keep, which is the only kind worth drawing.
 */
function GhostBoard() {
  return (
    <div
      aria-hidden
      className="mb-[30px] w-full max-w-[330px] rounded-card border border-dashed border-border px-[15px] py-3.5 opacity-60"
    >
      <div className="flex items-center gap-2">
        {/* The one shape in the ghost that is not a bar or a block: a widget's
            own marker, rotated square, in the accent. It is what tells the eye
            this grey rectangle is a titled card rather than a paragraph. */}
        <span className="size-[11px] flex-none rotate-45 rounded-[1.5px] border-2 border-primary" />
        <i className="block h-[7px] w-[86px] rounded-pill bg-foreground/[0.12]" />
        <i className="ml-auto block h-[7px] w-[34px] rounded-pill bg-foreground/[0.07]" />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-[7px]">
        <i className="block h-[30px] rounded-lg bg-foreground/[0.05]" />
        <i className="block h-[30px] rounded-lg bg-foreground/[0.05]" />
        <i className="block h-[30px] rounded-lg bg-foreground/[0.05]" />
      </div>

      <div className="mt-3 flex h-11 items-end gap-1">
        {GHOST_BARS.map((height, index) => (
          <i
            key={index}
            style={{ height: `${height}%` }}
            className={`block flex-1 rounded-t-[2px] ${
              height === GHOST_ACCENT ? "bg-primary/45" : "bg-foreground/[0.07]"
            }`}
          />
        ))}
      </div>
    </div>
  )
}
