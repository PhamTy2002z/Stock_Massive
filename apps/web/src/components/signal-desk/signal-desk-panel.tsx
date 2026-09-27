"use client"

/**
 * The right-hand pane once a Signal Desk answer has something to show.
 *
 * Four states and one seam, and the seam is what the file is really about: the
 * chart runtime is reached through **dynamic `import()` inside an effect**, not
 * through a top-level import. Chat never renders this component, so Chat never
 * evaluates the effect, so ECharts and the Flint compiler never enter the
 * bundle a chat-only reader downloads. A static import here would put a
 * charting library in the critical path of a surface that has no chart.
 *
 * **Nothing here edits what Flint compiled.** The option goes from
 * `compileVisual` into exactly one `setOption` call and is never stored, cloned,
 * serialised or walked. The host's whole contribution to the picture is the
 * width and height of the box it is drawn in.
 *
 * **Reduced motion is honoured without touching the option.** The preference is
 * carried by a registered theme whose only property is `animation: false` —
 * themes merge *under* the option, so every colour, axis and label Flint chose
 * still wins, and a reader who asked their system for stillness gets it.
 *
 * A compile failure is a value rather than an exception (`compile-visual.ts`
 * returns `null`), and the boundary around the chart is for the throw that is
 * not ours: this pane may fail without the conversation beside it failing.
 */

import { useEffect, useRef, useState } from "react"
import { ErrorBoundary } from "react-error-boundary"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { motionReduced } from "@/lib/alpha-desk/preferences"
import type { DeskView } from "@/lib/alpha-desk/desk-visual"
import type { CompiledPart, CompiledVisual } from "@/lib/flint/compile-visual"
import type { VisualPart } from "@/lib/alpha-desk/types"

import { SignalDeskEmpty } from "./signal-desk-empty"

/** The theme that carries one preference and nothing else. */
const STILL_THEME = "vg-still"

/** What the pane is doing while the compiler is still being fetched. */
type Compilation = { status: "pending" } | { status: "ready"; part: CompiledPart } | { status: "failed" }

export function SignalDeskPanel({ view }: { view: DeskView }) {
  if (view.state === "empty") return <SignalDeskEmpty />
  if (view.state === "working") return <Working />
  if (view.state === "none") return <NoChart />
  return (
    <ErrorBoundary fallback={<PaneNote>{SIGNAL_DESK_COPY.chartFailed}</PaneNote>}>
      <Chart visual={view.visual} />
    </ErrorBoundary>
  )
}

/**
 * A Turn is running, so the pane says so and shows no chart at all.
 *
 * Deliberately not the previous answer's chart dimmed: a picture on screen
 * under a new question is read as an answer to that question, and dimming is
 * not a strong enough denial.
 */
function Working() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy
      aria-label={SIGNAL_DESK_COPY.chartWorking}
      className="m-auto flex w-full max-w-[460px] flex-col gap-3"
    >
      <div className="h-[260px] w-full animate-pulse rounded-card bg-foreground/[0.05] motion-reduce:animate-none" />
      <div className="h-[110px] w-full animate-pulse rounded-card bg-foreground/[0.05] motion-reduce:animate-none" />
      <p className="text-center text-meta text-ink-6">{SIGNAL_DESK_COPY.chartWorking}</p>
    </div>
  )
}

function NoChart() {
  return <PaneNote>{SIGNAL_DESK_COPY.chartAbsent}</PaneNote>
}

function PaneNote({ children }: { children: React.ReactNode }) {
  return (
    <p role="status" aria-live="polite" className="m-auto max-w-[42ch] text-center text-meta text-ink-6">
      {children}
    </p>
  )
}

/**
 * One visual part, compiled and drawn.
 *
 * The compiler arrives with the chart runtime rather than with the page, so the
 * first frame of this component is a pending one even when the payload is
 * already in hand. That is the cost of keeping the library out of Chat's
 * bundle, and it is paid once per session.
 */
function Chart({ visual }: { visual: VisualPart }) {
  const [compilation, setCompilation] = useState<Compilation>({ status: "pending" })

  useEffect(() => {
    let live = true
    setCompilation({ status: "pending" })
    void import("@/lib/flint/compile-visual")
      .then(({ compileVisual }) => {
        if (!live) return
        const part = compileVisual(visual)
        setCompilation(part === null ? { status: "failed" } : { status: "ready", part })
      })
      .catch(() => {
        if (live) setCompilation({ status: "failed" })
      })
    return () => {
      live = false
    }
  }, [visual])

  if (compilation.status === "pending") return <Working />
  if (compilation.status === "failed") return <PaneNote>{SIGNAL_DESK_COPY.chartFailed}</PaneNote>

  return (
    <figure role="figure" aria-label={compilation.part.title} className="flex w-full flex-col gap-2">
      <figcaption className="text-meta text-ink-6">{compilation.part.title}</figcaption>
      {compilation.part.charts.map((chart, index) => (
        <Canvas key={index} chart={chart} />
      ))}
      <p className="text-micro text-ink-6">
        {SIGNAL_DESK_COPY.chartProvenance(visual.evidenceIds.length, visual.asOf)}
      </p>
    </figure>
  )
}

/**
 * One compiled option on one canvas, and the only place `setOption` is called.
 *
 * The instance is created, given the option once, resized with its box and
 * disposed when the pane closes. Nothing reads the option back out, and nothing
 * keeps it: a stored ECharts option would be a second copy of the answer that
 * could drift from the evidence the part names.
 */
function Canvas({ chart }: { chart: CompiledVisual }) {
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = box.current
    if (element === null) return
    let disposed = false
    let instance: { setOption: (option: unknown) => void; resize: () => void; dispose: () => void } | null = null
    let observer: ResizeObserver | null = null

    void import("echarts")
      .then((echarts) => {
        if (disposed || box.current === null) return
        const still = motionReduced()
        if (still) echarts.registerTheme(STILL_THEME, { animation: false })
        instance = echarts.init(element, still ? STILL_THEME : undefined, {
          renderer: "canvas",
        })
        instance.setOption(chart.option)
        observer = new ResizeObserver(() => instance?.resize())
        observer.observe(element)
      })
      .catch(() => {
        // A chunk that did not load, or a renderer that could not start on this
        // browser, is a pane with no picture in it. The answer and its sources
        // are in the column to the left and are unaffected — which is the whole
        // reason the chart is a sibling of the answer rather than part of it.
        instance = null
      })

    return () => {
      disposed = true
      observer?.disconnect()
      try {
        instance?.dispose()
      } catch {
        // Tearing down a renderer that never fully started. Nothing is left to
        // clean up, and throwing here would take the pane's unmount with it.
      }
    }
  }, [chart])

  return <div ref={box} style={{ height: chart.height }} className="w-full" />
}
