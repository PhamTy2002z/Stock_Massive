"use client"

/**
 * A board: the figures that lead it, the sections under them, the table at the end.
 *
 * **The arrangement is the server's and this honours it.** Which two charts are
 * a pair, which one takes the width, which figures lead — all decided by the
 * compiler, because they are claims about the analysis rather than about the
 * screen. Exactly one thing is decided here: a panel too narrow for thirds,
 * through `layout.ts`, which mirrors the server's own table.
 *
 * **The panel is measured, not the viewport.** The inspector is a column the
 * reader drags, so a media query asks the wrong question — at 420 pixels of
 * panel on a wide screen every breakpoint says "wide". A `ResizeObserver` on the
 * board's own box is what the collapse rule reads.
 *
 * **A board the server drew says so.** One line under the header, never omitted:
 * a board nobody claims authorship of is read by the reader as an argument
 * somebody made, and the server did not make one — it arranged what was there.
 */

import { useEffect, useRef, useState } from "react"

import type { Frame, Provenance, SignalDeskSpecV2 } from "@/lib/alpha-desk/types"

import { BoardSectionView } from "./board-section"
import { KpiStrip } from "./kpi-strip"
import { NARROW } from "./layout"
import { ProvenanceStrip } from "./provenance-strip"
import { SignalDeskBlockView } from "./signal-desk-block"

/**
 * What the board assumes before it has measured itself.
 *
 * The wide reading, deliberately: the first paint then matches the server's
 * arrangement, and the only correction is downward on a narrow panel. Starting
 * narrow would make every wide reader watch the board re-lay out once.
 */
const ASSUMED_WIDTH = NARROW

export function SignalDeskBoardView({
  spec,
  frames,
  provenance,
}: {
  spec: SignalDeskSpecV2
  frames: Record<string, Frame>
  provenance: Provenance
}) {
  const box = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(ASSUMED_WIDTH)

  useEffect(() => {
    const node = box.current
    if (node === null || typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0]?.contentRect.width
      if (typeof measured === "number" && measured > 0) setWidth(measured)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={box}>
      <h3 className="text-pretty text-[1.32rem] font-medium tracking-[-0.015em] text-ink-1">
        {spec.title}
      </h3>

      <ProvenanceStrip provenance={provenance} />

      {spec.autoComposed && (
        <p className="mt-1.5 text-meta text-muted-foreground">
          Bảng được dựng tự động từ dữ liệu đã tính.
        </p>
      )}

      <div className="mt-3.5 space-y-4 motion-safe:animate-vg-fade-in">
        <KpiStrip kpis={spec.kpis} width={width} />

        {spec.sections.map((section, index) => (
          <BoardSectionView
            key={index}
            section={section}
            frames={frames}
            provenance={provenance}
            width={width}
          />
        ))}

        {spec.appendix !== null && (
          <section>
            <h4 className="mb-2 text-meta font-medium uppercase tracking-[0.06em] text-muted-foreground">
              Số liệu đầy đủ
            </h4>
            <SignalDeskBlockView
              block={{
                widget: spec.appendix.widget,
                widgetVersion: spec.appendix.widgetVersion,
                frame: spec.appendix.frame,
                options: spec.appendix.options,
              }}
              frame={frames[spec.appendix.frame]}
              provenance={provenance}
            />
          </section>
        )}
      </div>
    </div>
  )
}
